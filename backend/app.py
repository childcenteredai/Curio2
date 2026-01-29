import base64
import io
import json
import os
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import quote_plus

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS
from openai import OpenAI
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import scoped_session, sessionmaker

from models import Conversation, Message
from prompts.eval import reflection, scaffolding, scienceqa
from prompts.scienceqa import level_0, level_1, level_2, level_3, level_4, no_question

load_dotenv()
app = Flask(__name__)


def decode_jwt(token):
    """Decode JWT token without signature verification."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None

        # JWT payload is base64url encoded (may be missing padding)
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        payload_bytes = base64.urlsafe_b64decode(padded.encode("utf-8"))
        return json.loads(payload_bytes.decode("utf-8"))
    except Exception as e:
        print(f"Error decoding JWT: {e}")
        return None


def get_user_from_request(request):
    """
    Extract user info from JWT in the header defined by ID_TOKEN_HEADER_NAME env var.

    Expected payload fields:
      - userId: payload.sub
      - email: payload.email
      - username: payload.preferred_username or payload.name
      - groups: payload.groups (list)

    Returns:
      dict with keys: userId, email, username, groups
      or None if token is missing/invalid.
    """
    header_name = os.getenv("ID_TOKEN_HEADER_NAME", "x-id-token")
    token = request.headers.get(header_name)

    if not token:
        return None

    payload = decode_jwt(token)
    if not payload or not payload.get("sub"):
        return None

    return {
        "userId": payload.get("sub"),
        "email": payload.get("email"),
        "username": payload.get("preferred_username") or payload.get("name"),
        "groups": payload.get("groups") or [],
    }


# CORS configuration - allow both dev server and Docker frontend
allowed_origins = [
    "http://localhost",  # Docker frontend (localhost without port)
    "http://localhost:80",  # Docker frontend (default nginx port)
    "http://localhost:5173",  # Development frontend
    "http://localhost:8080",  # Common Docker mapped port
]
if os.getenv("VUE_APP_URL"):
    allowed_origins.append(os.getenv("VUE_APP_URL"))
CORS(app, resources={r"/*": {"origins": allowed_origins}})

# Initialize OpenAI client
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("OPENAI_API_KEY environment variable is not set")
client = OpenAI(api_key=openai_api_key)

# OpenAI Model Configuration
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4")
OPENAI_WHISPER_MODEL = os.getenv("OPENAI_WHISPER_MODEL", "whisper-1")
OPENAI_TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "tts-1")
OPENAI_TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "alloy")
OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "500"))

# Database setup
# Prioritize POSTGRES_* environment variables (set by docker-compose) over DATABASE_URL
# This ensures we use the correct values even if DATABASE_URL is set incorrectly in .env
postgres_user = os.getenv("POSTGRES_USER")
postgres_password = os.getenv("POSTGRES_PASSWORD")
postgres_host = os.getenv("POSTGRES_HOST")
postgres_port = os.getenv("POSTGRES_PORT")
postgres_db = os.getenv("POSTGRES_DB")

# If POSTGRES_* variables are set (e.g., in Docker), construct URL from them
# Otherwise, try to use DATABASE_URL from environment
if postgres_user and postgres_password and postgres_host and postgres_db:
    # Construct DATABASE_URL from individual components
    if not postgres_port:
        postgres_port = "5432"
    # URL encode password in case it contains special characters
    encoded_password = quote_plus(postgres_password)
    database_url = f"postgresql://{postgres_user}:{encoded_password}@{postgres_host}:{postgres_port}/{postgres_db}"
    # Debug: print connection info (mask password)
    print("Constructed DATABASE_URL from POSTGRES_* environment variables")
    print(
        f"  User: {postgres_user}, Host: {postgres_host}, Port: {postgres_port}, Database: {postgres_db}"
    )
else:
    # Fall back to DATABASE_URL if POSTGRES_* variables are not set
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        # Last resort: use defaults
        postgres_user = postgres_user or "curio"
        postgres_password = postgres_password or "curio_password"
        postgres_host = postgres_host or "postgres"
        postgres_port = postgres_port or "5432"
        postgres_db = postgres_db or "curio_db"
        encoded_password = quote_plus(postgres_password)
        database_url = f"postgresql://{postgres_user}:{encoded_password}@{postgres_host}:{postgres_port}/{postgres_db}"
        print("Constructed DATABASE_URL from defaults")
    else:
        print("Using DATABASE_URL from environment")

engine = create_engine(database_url, pool_pre_ping=True)
SessionLocal = scoped_session(
    sessionmaker(bind=engine, autocommit=False, autoflush=False)
)

# Global variable to track conversation start times
conversation_start_times = {}

# System prompt for Curio
CURIO_SYSTEM_PROMPT = """
<System Introduction>
You are Curio, a friendly and encouraging science chatbot for children aged 8-10. The system shows an image, and your task is to prompt the child to discover the scientific phenomenon behind the image. Once the child has discovered the scientific phenomenon, you will prompt the child to ask questions to discover the science knowledge behind the phenomenon.
</System Introduction>
"""

state_history = defaultdict(list)
scienceqa_history = defaultdict(list)


def state_classification(state, messages, phenomenon):
    # Load prompt from the txt file
    if state in ["greet", "scaffolding"]:
        eval_prompt = format_prompt(scaffolding, phenomenon, messages)
    elif state in ["discover", "scienceqa"]:
        eval_prompt = format_prompt(scienceqa, phenomenon, messages)
    elif state in ["reflection"]:
        eval_prompt = format_prompt(reflection, phenomenon, messages)

    messages = [{"role": "system", "content": eval_prompt}]
    # print(f"messages: {messages}")

    response = client.chat.completions.create(
        model=OPENAI_CHAT_MODEL, messages=messages, max_tokens=OPENAI_MAX_TOKENS
    )

    # response = client.responses.create(
    #         model="gpt-5",
    #         input = messages,
    #         reasoning={ "effort": "low" },
    #     )

    # content = response.output_text or ""
    content = response.choices[0].message.content or ""
    eval_state = content.strip().lower().replace("<", "").replace(">", "")
    return eval_state


def state_update(current_state, eval_state, state_history_list):
    ## removed reflection state for pilot testing
    next_state = eval_state
    if eval_state == "discover":
        next_state = "discover"
    elif eval_state == "scienceqa":
        if len(state_history_list) > 0 and state_history_list[-1] == "scaffolding":
            next_state = "discover"
        elif "reflection" not in state_history_list:
            # total_sci = state_history_list.count("scienceqa")
            # if total_sci >= 2:
            #     next_state = "reflection"
            # else:
            #     next_state = "scienceqa"
            next_state = "scienceqa"
        else:
            # reflection_index = state_history_list.index("reflection")
            # post_ref_sci = state_history_list[reflection_index:].count("scienceqa")
            num_of_reflection = state_history_list.count("reflection")
            if num_of_reflection >= 2:
                next_state = "close"
            else:
                # next_state = "reflection" if post_ref_sci >= 2 else "scienceqa"
                next_state = "scienceqa"
    elif eval_state == "reflection":
        next_state = "reflection"
    elif eval_state == "scaffolding":
        num_of_scaffolding = state_history_list.count("scaffolding")
        if num_of_scaffolding >= 1:
            next_state = "discover"
        else:
            next_state = "scaffolding"
    elif eval_state == "close":
        next_state = "close"
    else:
        next_state = "scienceqa"

    state_history_list.append(next_state)
    return next_state


def state_prompt_classification(state, child_question_level=None):
    if state == "greet":
        return open("prompts/greet.txt", "r").read()
    elif state == "scaffolding":
        return open("prompts/scaffolding.txt", "r").read()
    elif state == "discover":
        return open("prompts/discover.txt", "r").read()
    elif state == "scienceqa":
        if child_question_level == "no_question":
            return no_question
        elif child_question_level == "irrelevant":
            return level_0
        elif child_question_level == "factual":
            return level_1
        elif child_question_level == "explanatory":
            return level_2
        elif child_question_level == "general_causal":
            return level_3
        elif child_question_level == "specific_causal":
            return level_4
    elif state == "reflection":
        return open("prompts/reflection.txt", "r").read()
    elif state == "close":
        return open("prompts/close.txt", "r").read()
    else:
        return open("prompts/scienceqa.txt", "r").read()


def format_prompt(
    state_prompt, phenomenon="balloon", messages=None, child_question_level=None
):
    if messages is None:
        messages = []

    phenomenon_json = json.load(open("prompts/phenomenon.json", "r"))
    phenomenon_data = phenomenon_json.get(phenomenon, {})

    if "<Image Content>" in state_prompt:
        state_prompt = state_prompt.replace(
            "<Image Content>",
            "<Image Content>\n" + phenomenon_data.get("image_content", ""),
        )
    if "<Scientific Phenomenon>" in state_prompt:
        state_prompt = state_prompt.replace(
            "<Scientific Phenomenon>",
            "<Scientific Phenomenon>\n" + phenomenon_data.get("phenomenon", ""),
        )
    if "<Scientific Knowledge>" in state_prompt:
        state_prompt = state_prompt.replace(
            "<Scientific Knowledge>",
            "<Scientific Knowledge>\n" + phenomenon_data.get("knowledge", ""),
        )

    if "<Mechanism Context>" in state_prompt:
        # Load mechanism from kg.json
        knowledge_base = json.load(open("knowledge/kg.json", "r"))
        phenomenon_map = {
            "balloon": "Hair stands up near a balloon",
            "bend": "Bending Water Stream with a Comb",
            "pepper": "Pepper Leaping up to Spoon",
        }
        phenomenon_key = phenomenon_map.get(phenomenon, "Hair stands up near a balloon")
        mechanism = knowledge_base.get(phenomenon_key, {}).get("mechanism", "")
        state_prompt = state_prompt.replace(
            "<Mechanism Context>",
            "<Mechanism Context>\n" + mechanism,
        )

    if "{kg_concepts}" in state_prompt:
        # Load knowledge base and extract all concepts and sub-concepts
        knowledge_base = json.load(open("knowledge/kg.json", "r"))
        phenomenon_map = {
            "balloon": "Hair stands up near a balloon",
            "bend": "Bending Water Stream with a Comb",
            "pepper": "Pepper Leaping up to Spoon",
        }
        phenomenon_key = phenomenon_map.get(phenomenon, "Hair stands up near a balloon")
        concepts_dict = knowledge_base.get(phenomenon_key, {}).get("concepts", {})
        all_concepts = extract_all_concepts_and_subconcepts(concepts_dict)

        # Format the list as a comma-separated string for inline insertion
        concepts_list_str = ", ".join(all_concepts)
        state_prompt = state_prompt.replace("{kg_concepts}", concepts_list_str)

    if "<Child's Question>" in state_prompt:
        state_prompt = state_prompt.replace(
            "<Child's Question>",
            "<Child's Question>\n" + messages[-1]["content"].strip(),
        )
    if "<Conversation History>" in state_prompt:
        state_prompt = state_prompt.replace(
            "<Conversation History>", "<Conversation History>\n" + json.dumps(messages)
        )
    return state_prompt


def build_structured_kg(concepts_dict):
    """
    Build a structured knowledge graph showing concept/sub-concept hierarchy.
    Returns a dictionary with concepts and their sub-concepts.
    """
    structured_kg = {}
    for concept_name, concept_data in concepts_dict.items():
        structured_kg[concept_name] = {}
        if "sub_concepts" in concept_data and concept_data["sub_concepts"]:
            sub_concepts_list = []
            for sub_concept_name, sub_concept_data in concept_data[
                "sub_concepts"
            ].items():
                sub_concept_entry = {"name": sub_concept_name}
                # Check if this sub-concept has its own sub-concepts
                if (
                    "sub_concepts" in sub_concept_data
                    and sub_concept_data["sub_concepts"]
                ):
                    sub_concept_entry["sub-concepts"] = list(
                        sub_concept_data["sub_concepts"].keys()
                    )
                sub_concepts_list.append(sub_concept_entry)
            structured_kg[concept_name]["sub-concepts"] = sub_concepts_list
        else:
            structured_kg[concept_name]["sub-concepts"] = []
    return structured_kg


def extract_all_concepts_and_subconcepts(concepts_dict):
    """
    Extract all concept and sub-concept names from the knowledge graph.
    Returns a flat list of all concept and sub-concept names.
    """
    all_concepts = []

    def extract_recursive(concept_data, parent_name=None):
        """Recursively extract all concept and sub-concept names."""
        if isinstance(concept_data, dict):
            for key, value in concept_data.items():
                if key == "sub_concepts" and isinstance(value, dict):
                    for sub_concept_name, sub_concept_data in value.items():
                        all_concepts.append(sub_concept_name)
                        # Recursively extract nested sub-concepts
                        if (
                            isinstance(sub_concept_data, dict)
                            and "sub_concepts" in sub_concept_data
                        ):
                            extract_recursive(sub_concept_data, sub_concept_name)

    for concept_name, concept_data in concepts_dict.items():
        all_concepts.append(concept_name)
        extract_recursive(concept_data, concept_name)

    return all_concepts


def knowledge_retrieval(messages, phenomenon="balloon"):
    # Load prompt from the txt file
    retrieval_prompt = open("prompts/knowledge_matching.txt", "r").read()
    retrieval_prompt = format_prompt(retrieval_prompt, phenomenon, messages)
    knowledge_base = open("knowledge/kg.json", "r").read()
    knowledge_base = json.loads(knowledge_base)

    # Map phenomenon to knowledge base key
    phenomenon_map = {
        "balloon": "Hair stands up near a balloon",
        "bend": "Bending Water Stream with a Comb",
        "pepper": "Pepper Leaping up to Spoon",
    }
    phenomenon_key = phenomenon_map.get(phenomenon, "Hair stands up near a balloon")

    # Build structured KG with concept/sub-concept hierarchy
    concepts_dict = knowledge_base[phenomenon_key]["concepts"]
    structured_kg = build_structured_kg(concepts_dict)

    # Calculate conversation turn count (each user message + assistant response = 1 turn)
    # Count user messages as turns
    turn_count = sum(1 for msg in messages if msg.get("role") == "user")

    # Add structured KG information to the prompt
    retrieval_prompt = (
        retrieval_prompt
        + "\n\n<Knowledge Graph Structure (concepts with their sub-concepts)>\n"
        + json.dumps(structured_kg, indent=2)
        + "\n</Knowledge Graph Structure>"
        + f"\n\n<Conversation Turn Count>\nCurrent turn: {turn_count}\n</Conversation Turn Count>"
    )

    # print(f"retrieval_prompt: {retrieval_prompt}")
    messages = [{"role": "system", "content": retrieval_prompt}]
    response = client.chat.completions.create(
        model=OPENAI_CHAT_MODEL, messages=messages, max_tokens=OPENAI_MAX_TOKENS
    )

    # response = client.responses.create(
    #         model="gpt-5",
    #         input = messages,
    #         reasoning={ "effort": "low" }
    #     )

    # content = response.output_text or ""
    content = response.choices[0].message.content or ""
    kg_raw = content.strip().lower()
    # print(f"kg_raw: {kg_raw}")
    return kg_raw


def format_kg(mode="definition", kg_raw="", phenomenon="balloon"):
    knowledge_base = open("knowledge/kg.json", "r").read()
    knowledge_base = json.loads(knowledge_base)

    # Map phenomenon to knowledge base key
    phenomenon_map = {
        "balloon": "Hair stands up near a balloon",
        "bend": "Bending Water Stream with a Comb",
        "pepper": "Pepper Leaping up to Spoon",
    }
    phenomenon_key = phenomenon_map.get(phenomenon, "Hair stands up near a balloon")

    try:
        kg_list = json.loads(kg_raw)

        # Only use the FIRST component (most relevant one)
        # Do not process multiple components
        if not kg_list or len(kg_list) == 0:
            return ""

        component = kg_list[0]  # Take only the first component

        # Verify the component exists in the knowledge base
        if component not in knowledge_base[phenomenon_key]["concepts"]:
            print(f"Warning: Component '{component}' not found in knowledge base")
            return ""

        # Get the component data (do NOT include sub_concepts)
        component_data = knowledge_base[phenomenon_key]["concepts"][component]
        definition = component_data.get("definition", "")
        explanation = component_data.get("explanation", "")

        # Format the single component (without sub_concepts)
        if mode == "definition":
            kg_content = f"'{component}':\n\nDefinition: {definition}\n\n"
        elif mode == "explanation":
            kg_content = f"'{component}':\n\nExplanation: {explanation}\n\n"
        elif mode == "definition_and_explanation":
            kg_content = f"'{component}':\n\nDefinition: {definition}\n\nExplanation: {explanation}\n\n"
        else:
            kg_content = ""

        kg_content = kg_content.strip()
        print(f"kg_content: {kg_content}")
        return kg_content
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Error processing knowledge graph: {e}")
        return ""


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def check_moderation(text):
    """
    Check if text contains harmful content using OpenAI's moderation API.
    Returns (is_flagged, categories) tuple where:
    - is_flagged: True if content is flagged as harmful
    - categories: Dict of category flags if content is harmful
    """
    try:
        moderation_response = client.moderations.create(input=text)
        result = moderation_response.results[0]
        return result.flagged, result.categories
    except Exception as e:
        app.logger.error(f"Moderation check error: {str(e)}")
        # If moderation fails, we'll allow the message through but log the error
        # You may want to change this behavior based on your security requirements
        return False, {}


def fix_scienceqa_bold_formatting(text):
    """
    Fix bold formatting in scienceqa responses.
    Rules:
    1. Single asterisks (*text*) should be converted to double asterisks (**text**)
    2. Multi-word phrases should have each word separately bolded: **word1** **word2**
    3. Ensure all bold markers are properly paired

    Args:
        text: Text that may have incorrect bold formatting

    Returns:
        Text with corrected bold formatting
    """
    if not text:
        return ""

    import re

    # Step 1: Fix single asterisks (*text*) to double asterisks (**text**)
    # Match single asterisks that are not already part of **
    # Pattern: *word* but not **word** or *word** or **word*
    def fix_single_asterisks(match):
        content = match.group(1)
        # If it's a multi-word phrase, split and bold each word separately
        words = content.split()
        if len(words) > 1:
            return " ".join([f"**{word}**" for word in words])
        else:
            return f"**{content}**"

    # Replace single asterisks (not part of double asterisks)
    # This regex matches *word* but avoids matching **word** or *word** or **word*
    text = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", fix_single_asterisks, text)

    # Step 2: Fix multi-word phrases that are bolded together (**word1 word2**)
    # Convert to **word1** **word2**
    def fix_multiword_bold(match):
        content = match.group(1)
        words = content.split()
        if len(words) > 1:
            return " ".join([f"**{word}**" for word in words])
        else:
            return match.group(0)  # Keep original if single word

    # Match **word1 word2 word3** patterns
    text = re.sub(r"\*\*([^*]+?)\*\*", fix_multiword_bold, text)

    # Step 3: Fix any remaining unpaired asterisks
    # Count asterisks and ensure they're paired
    # Remove any single asterisks that aren't part of a pair
    text = re.sub(r"(?<!\*)\*(?!\*)", "", text)

    return text


def clean_text_for_speech(text):
    """
    Clean markdown formatting from text for TTS generation.
    Removes markdown bold markers (**text**) while preserving the text content.
    This ensures TTS can generate speech without interruption from formatting markers.

    Args:
        text: Text with markdown formatting

    Returns:
        Cleaned text suitable for TTS
    """
    if not text:
        return ""

    # Remove markdown bold markers (**text**)
    # This handles both **text** and **text** **text** patterns
    cleaned = text.replace("**", "")

    # Optionally clean other markdown formatting if needed
    # Remove markdown italic markers (*text* or _text_)
    # But be careful - single * might be used for emphasis in speech
    # For now, we only remove ** (double asterisks) as requested

    return cleaned


@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return (
        jsonify(
            {
                "status": "healthy",
                "service": "curio2-backend",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ),
        200,
    )


@app.route("/api/transcribe", methods=["POST"])
def transcribe_audio():
    """Transcribe audio using OpenAI Whisper API"""
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file_storage = request.files["audio"]

    try:
        # Read the file content as bytes
        audio_bytes = audio_file_storage.read()

        # Create a BytesIO object from the bytes
        audio_file = io.BytesIO(audio_bytes)

        # Get filename or use default
        filename = audio_file_storage.filename or "audio.webm"

        # Call OpenAI Whisper API from backend
        # OpenAI API expects (filename, file-like object) tuple
        transcript = client.audio.transcriptions.create(
            model=OPENAI_WHISPER_MODEL,
            file=(filename, audio_file),
            response_format="json",
            language="en",
        )

        return jsonify({"text": transcript.text}), 200

    except Exception as e:
        app.logger.error(f"Transcription error: {str(e)}")
        return jsonify({"error": "Transcription failed"}), 500


@app.route("/api/chat", methods=["POST"])
def chat_completion():
    """Generate chat response and a next_state using OpenAI"""
    db = SessionLocal()
    try:
        # Extract user info from JWT (if available)
        user_info = get_user_from_request(request)

        # Record start time for latency tracking
        start_time = time.time()
        request_session_id = request.remote_addr  # Fallback session identifier
        conversation_start_times[request_session_id] = start_time

        data = request.get_json()
        messages = data.get("messages", [])
        state = (data.get("state") or "greet").strip()
        image_path = data.get("image_path", "")  # Get the selected image path
        session_identifier = (
            data.get("session_id") or request_session_id or ""
        ).strip()
        conversation_id = (data.get("conversation_id") or str(uuid.uuid4())).strip()
        user_audio_b64 = data.get("user_audio")
        user_audio_mime_type = data.get("user_audio_mime_type")

        user_audio_bytes = None
        if user_audio_b64:
            try:
                user_audio_bytes = base64.b64decode(user_audio_b64)
            except (ValueError, TypeError) as audio_error:
                print(
                    f"Failed to decode user audio for conversation {conversation_id}: {audio_error}"
                )

        latest_user_message = ""
        if messages:
            last_message = messages[-1]
            if last_message.get("role") == "user":
                latest_user_message = last_message.get("content", "")

        # Determine the phenomenon based on image path
        if "balloon.jpg" in image_path:
            phenomenon = "balloon"
        elif "bend.jpg" in image_path:
            phenomenon = "bend"
        elif "pepper.jpg" in image_path:
            phenomenon = "pepper"
        else:
            phenomenon = "balloon"  # default fallback

        conversation = db.get(Conversation, conversation_id)
        if not conversation:
            # Use the provided session_identifier, or generate a new one if not provided
            final_session_id = (
                session_identifier if session_identifier else str(uuid.uuid4())
            )
            print(
                f"Creating new conversation {conversation_id} with session_id: {final_session_id}"
            )

            # Prepare user info for database (optional, only if token is present)
            user_groups_json = None
            if user_info and user_info.get("groups"):
                try:
                    user_groups_json = json.dumps(user_info["groups"])
                except (TypeError, ValueError):
                    user_groups_json = None

            conversation = Conversation(
                id=conversation_id,
                session_id=final_session_id,
                image_path=image_path,
                phenomenon=phenomenon,
                user_id=user_info.get("userId") if user_info else None,
                user_email=user_info.get("email") if user_info else None,
                username=user_info.get("username") if user_info else None,
                user_groups=user_groups_json,
                started_at=datetime.utcnow(),
            )
            db.add(conversation)
            # Commit conversation immediately so it exists when messages are added
            try:
                db.commit()
                print(
                    f"Successfully created conversation {conversation_id} with session_id: {final_session_id}"
                )
            except Exception as commit_error:
                db.rollback()
                print(f"Error committing conversation: {commit_error}")
                raise
        else:
            print(
                f"Found existing conversation {conversation_id} with session_id: {conversation.session_id}"
            )
            # Backfill user info if it is missing and we have it from JWT
            if user_info and not conversation.user_id:
                conversation.user_id = user_info.get("userId")
                conversation.user_email = user_info.get("email")
                conversation.username = user_info.get("username")
                if user_info.get("groups"):
                    try:
                        conversation.user_groups = json.dumps(user_info["groups"])
                    except (TypeError, ValueError):
                        pass
            # Commit conversation immediately so it exists when messages are added
            try:
                db.commit()
            except Exception as commit_error:
                db.rollback()
                print(f"Error committing conversation: {commit_error}")
                raise

        # Check for harmful content in user message (after conversation is created)
        if latest_user_message:
            is_flagged, categories = check_moderation(latest_user_message)
            if is_flagged:
                # Log the moderation event
                # Extract flagged categories from the categories object
                # Categories object has boolean attributes for each category
                flagged_categories = []
                if hasattr(categories, "__dict__"):
                    flagged_categories = [
                        cat
                        for cat, flagged in vars(categories).items()
                        if isinstance(flagged, bool) and flagged
                    ]
                else:
                    # Fallback: try common category names
                    common_categories = [
                        "hate",
                        "hate_threatening",
                        "harassment",
                        "harassment_threatening",
                        "self_harm",
                        "self_harm_intent",
                        "self_harm_instructions",
                        "sexual",
                        "sexual_minors",
                        "violence",
                        "violence_graphic",
                    ]
                    flagged_categories = [
                        cat
                        for cat in common_categories
                        if getattr(categories, cat, False)
                    ]
                app.logger.warning(
                    f"Moderation flagged message in conversation {conversation_id}: "
                    f"Categories: {flagged_categories}"
                )

                # Return a safe, child-friendly response
                safe_response = (
                    "I'm here to help you learn about science in a safe and positive way! "
                    "Let's focus on exploring the scientific phenomenon in the image. "
                    "What do you notice about what's happening?"
                )

                # Still save the user message to the database (for audit purposes)
                # but don't process it through the normal flow
                user_message_record = Message(
                    conversation_id=conversation.id,
                    role="user",
                    content=latest_user_message,
                    state=state,
                    evaluation_result="moderated",
                    matched_knowledge_components=None,
                    audio_data=user_audio_bytes,
                    audio_mime_type=user_audio_mime_type,
                )
                db.add(user_message_record)

                assistant_message_record = Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=safe_response,
                    state=state,
                )
                db.add(assistant_message_record)

                conversation.updated_at = datetime.utcnow()
                db.commit()

                return jsonify(
                    {"response": safe_response, "next_state": state, "moderated": True}
                )

        conv_state_history = state_history[conversation_id]
        conv_scienceqa_history = scienceqa_history[conversation_id]

        eval_state = None
        if state != "scienceqa":
            eval_state = state_classification(state, messages, phenomenon)
            current_state = state_update(state, eval_state, conv_state_history)

            # If transitioning to scienceqa, classify the question level immediately
            if current_state == "scienceqa":
                child_question_level = state_classification(state, messages, phenomenon)
                conv_scienceqa_history.append(child_question_level)
                print("\n=== Turn Evaluation (Non-Stream) ===")
                print(f"Child's Question: {latest_user_message}")
                print(f"Evaluation Result: {child_question_level}")
                print("=" * 50)
                state_prompt = state_prompt_classification(
                    current_state, child_question_level
                )
            else:
                child_question_level = None
                if latest_user_message:
                    print("\n=== Turn Evaluation (Non-Stream) ===")
                    print(f"Child's Question: {latest_user_message}")
                    print(f"Evaluation Result: {eval_state}")
                    print("=" * 50)
                state_prompt = state_prompt_classification(current_state)
        else:
            # Check if we should move to reflection based on qualified questions
            qualified_question_num = sum(
                1
                for question in conv_scienceqa_history
                if question in ["explanatory", "general_causal", "specific_causal"]
            )

            if qualified_question_num > 2:
                current_state = "reflection"
                state_prompt = state_prompt_classification(current_state)
                child_question_level = None
                if latest_user_message:
                    print("\n=== Turn Evaluation (Non-Stream) ===")
                    print(f"Child's Question: {latest_user_message}")
                    print("Evaluation Result: reflection")
                    print("=" * 50)
            else:
                # Classify the child's question level
                child_question_level = state_classification(state, messages, phenomenon)
                conv_scienceqa_history.append(child_question_level)
                print("\n=== Turn Evaluation (Non-Stream) ===")
                print(f"Child's Question: {latest_user_message}")
                print(f"Evaluation Result: {child_question_level}")
                current_state = "scienceqa"  # Stay in scienceqa state
                state_prompt = state_prompt_classification(
                    current_state, child_question_level
                )
            if not conv_state_history or conv_state_history[-1] != current_state:
                conv_state_history.append(current_state)
            eval_state = current_state

        # Track matched knowledge components for saving to database
        matched_kg = None
        if current_state in ["scienceqa", "reflection"]:
            if current_state == "scienceqa" and child_question_level in [
                "factual",
                "explanatory",
                "general_causal",
                "specific_causal",
            ]:
                kg = knowledge_retrieval(messages, phenomenon)
                matched_kg = kg  # Store for database
                print(
                    f"Matched Knowledge Components: {matched_kg if matched_kg else 'None'}"
                )
                print("=" * 50)
                if kg != "":
                    if child_question_level in [
                        "explanatory",
                        "general_causal",
                        "specific_causal",
                    ]:
                        state_prompt = (
                            state_prompt
                            + "\n\n<Relevant Knowledge Components>\n"
                            + format_kg("definition_and_explanation", kg, phenomenon)
                            + "\n</Relevant Knowledge Components>"
                        )
                    elif child_question_level == "factual":
                        state_prompt = (
                            state_prompt
                            + "\n\n<Relevant Knowledge Components>\n"
                            + format_kg("definition_and_explanation", kg, phenomenon)
                            + "\n</Relevant Knowledge Components>"
                        )
            elif current_state == "reflection":
                kg = knowledge_retrieval(messages, phenomenon)
                matched_kg = kg  # Store for database
                print(
                    f"Matched Knowledge Components: {matched_kg if matched_kg else 'None'}"
                )
                print("=" * 50)
                if kg != "":
                    state_prompt = (
                        state_prompt
                        + "\n\n<Relevant Knowledge Components>\n"
                        + format_kg("definition_and_explanation", kg, phenomenon)
                        + "\n</Relevant Knowledge Components>"
                    )

        if current_state == "scienceqa" and child_question_level is not None:
            state_prompt = format_prompt(
                state_prompt, phenomenon, messages, child_question_level
            )
        else:
            state_prompt = format_prompt(state_prompt, phenomenon, messages)

        user_evaluation_result = child_question_level or eval_state or current_state

        if latest_user_message:
            user_message_record = Message(
                conversation_id=conversation.id,
                role="user",
                content=latest_user_message,
                state=state,
                evaluation_result=user_evaluation_result,
                matched_knowledge_components=matched_kg if matched_kg else None,
                audio_data=user_audio_bytes,
                audio_mime_type=user_audio_mime_type,
            )
            db.add(user_message_record)
            # Commit user message immediately so it's saved
            try:
                db.commit()
                print(
                    f"Saved user message for conversation {conversation_id}: {latest_user_message[:50]}..."
                )
            except Exception as commit_error:
                db.rollback()
                print(f"Error committing user message: {commit_error}")
                raise

        conversation.image_path = image_path
        conversation.phenomenon = phenomenon
        conversation.updated_at = datetime.utcnow()
        if user_evaluation_result:
            conversation.evaluation_result = user_evaluation_result
        if current_state == "close" and not conversation.finished_at:
            conversation.finished_at = datetime.utcnow()
        if current_state == "close":
            state_history.pop(conversation_id, None)
            scienceqa_history.pop(conversation_id, None)

        system_message = {"role": "system", "content": CURIO_SYSTEM_PROMPT}

        all_messages = (
            [system_message] + messages + [{"role": "user", "content": state_prompt}]
        )

        response = client.chat.completions.create(
            model=OPENAI_CHAT_MODEL, messages=all_messages, max_tokens=OPENAI_MAX_TOKENS
        )

        content = response.choices[0].message.content or ""

        # Fix bold formatting for scienceqa responses
        if current_state == "scienceqa":
            original_content = content
            content = fix_scienceqa_bold_formatting(content)
            if content != original_content:
                print("Fixed bold formatting in scienceqa response")
                print(f"Original: {original_content[:100]}...")
                print(f"Fixed: {content[:100]}...")

        # Determine assistant evaluation result (only in scienceqa phase)
        assistant_evaluation_result = None
        if current_state == "scienceqa" and child_question_level:
            assistant_evaluation_result = child_question_level

        assistant_message_record = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=content,
            state=current_state,
            evaluation_result=assistant_evaluation_result,
            matched_knowledge_components=matched_kg if matched_kg else None,
        )
        db.add(assistant_message_record)

        # Commit assistant message (user message already committed above)
        try:
            db.commit()
            print(f"Saved assistant message for conversation {conversation_id}")
        except Exception as commit_error:
            db.rollback()
            print(
                f"Error committing assistant message for conversation {conversation_id}: {commit_error}"
            )
            import traceback

            print(traceback.format_exc())
            raise

        return jsonify({"response": content, "next_state": current_state})

    except SQLAlchemyError as db_error:
        db.rollback()
        print(f"Database error during chat completion: {db_error}")
        return jsonify({"error": "Chat completion failed"}), 500
    except Exception as e:
        db.rollback()
        print(f"Chat completion error: {e}")
        return jsonify({"error": "Chat completion failed"}), 500
    finally:
        db.close()


@app.route("/api/chat/stream", methods=["POST"])
def chat_completion_stream():
    """Generate chat response with streaming using OpenAI"""
    db = SessionLocal()
    try:
        # Extract user info from JWT (if available)
        user_info = get_user_from_request(request)

        # Record start time for latency tracking
        start_time = time.time()
        request_session_id = request.remote_addr
        conversation_start_times[request_session_id] = start_time

        data = request.get_json()
        messages = data.get("messages", [])
        state = (data.get("state") or "greet").strip()
        image_path = data.get("image_path", "")
        session_identifier = (
            data.get("session_id") or request_session_id or ""
        ).strip()
        conversation_id = (data.get("conversation_id") or str(uuid.uuid4())).strip()
        user_audio_b64 = data.get("user_audio")
        user_audio_mime_type = data.get("user_audio_mime_type")

        user_audio_bytes = None
        if user_audio_b64:
            try:
                user_audio_bytes = base64.b64decode(user_audio_b64)
            except (ValueError, TypeError) as audio_error:
                print(
                    f"Failed to decode user audio for conversation {conversation_id}: {audio_error}"
                )

        latest_user_message = ""
        if messages:
            last_message = messages[-1]
            if last_message.get("role") == "user":
                latest_user_message = last_message.get("content", "")

        # Determine the phenomenon based on image path
        if "balloon.jpg" in image_path:
            phenomenon = "balloon"
        elif "bend.jpg" in image_path:
            phenomenon = "bend"
        elif "pepper.jpg" in image_path:
            phenomenon = "pepper"
        else:
            phenomenon = "balloon"

        conversation = db.get(Conversation, conversation_id)
        if not conversation:
            # Use the provided session_identifier, or generate a new one if not provided
            final_session_id = (
                session_identifier if session_identifier else str(uuid.uuid4())
            )
            print(
                f"Creating new conversation {conversation_id} with session_id: {final_session_id}"
            )

            # Prepare user info for database (optional, only if token is present)
            user_groups_json = None
            if user_info and user_info.get("groups"):
                try:
                    user_groups_json = json.dumps(user_info["groups"])
                except (TypeError, ValueError):
                    user_groups_json = None

            conversation = Conversation(
                id=conversation_id,
                session_id=final_session_id,
                image_path=image_path,
                phenomenon=phenomenon,
                user_id=user_info.get("userId") if user_info else None,
                user_email=user_info.get("email") if user_info else None,
                username=user_info.get("username") if user_info else None,
                user_groups=user_groups_json,
                started_at=datetime.utcnow(),
            )
            db.add(conversation)
            # Commit conversation immediately so it exists when messages are added
            try:
                db.commit()
                print(
                    f"Successfully created conversation {conversation_id} with session_id: {final_session_id}"
                )
            except Exception as commit_error:
                db.rollback()
                print(f"Error committing conversation: {commit_error}")
                raise
        else:
            print(
                f"Found existing conversation {conversation_id} with session_id: {conversation.session_id}"
            )
            # Backfill user info if it is missing and we have it from JWT
            if user_info and not conversation.user_id:
                conversation.user_id = user_info.get("userId")
                conversation.user_email = user_info.get("email")
                conversation.username = user_info.get("username")
                if user_info.get("groups"):
                    try:
                        conversation.user_groups = json.dumps(user_info["groups"])
                    except (TypeError, ValueError):
                        pass

        # Check for harmful content
        if latest_user_message:
            is_flagged, categories = check_moderation(latest_user_message)
            if is_flagged:
                safe_response = (
                    "I'm here to help you learn about science in a safe and positive way! "
                    "Let's focus on exploring the scientific phenomenon in the image. "
                    "What do you notice about what's happening?"
                )

                user_message_record = Message(
                    conversation_id=conversation.id,
                    role="user",
                    content=latest_user_message,
                    state=state,
                    evaluation_result="moderated",
                    matched_knowledge_components=None,
                    audio_data=user_audio_bytes,
                    audio_mime_type=user_audio_mime_type,
                )
                db.add(user_message_record)

                assistant_message_record = Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=safe_response,
                    state=state,
                )
                db.add(assistant_message_record)

                conversation.updated_at = datetime.utcnow()
                db.commit()

                # Stream the safe response
                def generate():
                    yield f"data: {json.dumps({'type': 'token', 'content': safe_response})}\n\n"
                    yield f"data: {json.dumps({'type': 'done', 'response': safe_response, 'next_state': state})}\n\n"

                return Response(
                    stream_with_context(generate()), mimetype="text/event-stream"
                )

        conv_state_history = state_history[conversation_id]
        conv_scienceqa_history = scienceqa_history[conversation_id]

        eval_state = None
        if state != "scienceqa":
            eval_state = state_classification(state, messages, phenomenon)
            current_state = state_update(state, eval_state, conv_state_history)

            if current_state == "scienceqa":
                child_question_level = state_classification(state, messages, phenomenon)
                conv_scienceqa_history.append(child_question_level)
                print("\n=== Turn Evaluation (Stream) ===")
                print(f"Child's Question: {latest_user_message}")
                print(f"Evaluation Result: {child_question_level}")
                state_prompt = state_prompt_classification(
                    current_state, child_question_level
                )
            else:
                child_question_level = None
                if latest_user_message:
                    print("\n=== Turn Evaluation (Stream) ===")
                    print(f"Child's Question: {latest_user_message}")
                    print(f"Evaluation Result: {eval_state}")
                    print("=" * 50)
                state_prompt = state_prompt_classification(current_state)
        else:
            qualified_question_num = sum(
                1
                for question in conv_scienceqa_history
                if question in ["explanatory", "general_causal", "specific_causal"]
            )

            if qualified_question_num > 2:
                current_state = "reflection"
                state_prompt = state_prompt_classification(current_state)
                child_question_level = None
                if latest_user_message:
                    print("\n=== Turn Evaluation (Stream) ===")
                    print(f"Child's Question: {latest_user_message}")
                    print("Evaluation Result: reflection")
                    print("=" * 50)
            else:
                child_question_level = state_classification(state, messages, phenomenon)
                conv_scienceqa_history.append(child_question_level)
                print("\n=== Turn Evaluation (Stream) ===")
                print(f"Child's Question: {latest_user_message}")
                print(f"Evaluation Result: {child_question_level}")
                print("=" * 50)
                current_state = "scienceqa"
                state_prompt = state_prompt_classification(
                    current_state, child_question_level
                )
            if not conv_state_history or conv_state_history[-1] != current_state:
                conv_state_history.append(current_state)
            eval_state = current_state

        # Track matched knowledge components for saving to database
        matched_kg = None
        if current_state in ["scienceqa", "reflection"]:
            if current_state == "scienceqa" and child_question_level in [
                "factual",
                "explanatory",
                "general_causal",
                "specific_causal",
            ]:
                kg = knowledge_retrieval(messages, phenomenon)
                matched_kg = kg  # Store for database
                print(
                    f"Matched Knowledge Components: {matched_kg if matched_kg else 'None'}"
                )
                print("=" * 50)
                if kg != "":
                    if child_question_level in [
                        "explanatory",
                        "general_causal",
                        "specific_causal",
                    ]:
                        state_prompt = (
                            state_prompt
                            + "\n\n<Relevant Knowledge Components>\n"
                            + format_kg("definition_and_explanation", kg, phenomenon)
                            + "\n</Relevant Knowledge Components>"
                        )
                    elif child_question_level == "factual":
                        state_prompt = (
                            state_prompt
                            + "\n\n<Relevant Knowledge Components>\n"
                            + format_kg("definition_and_explanation", kg, phenomenon)
                            + "\n</Relevant Knowledge Components>"
                        )
            elif current_state == "reflection":
                kg = knowledge_retrieval(messages, phenomenon)
                matched_kg = kg  # Store for database
                print(
                    f"Matched Knowledge Components: {matched_kg if matched_kg else 'None'}"
                )
                print("=" * 50)
                if kg != "":
                    state_prompt = (
                        state_prompt
                        + "\n\n<Relevant Knowledge Components>\n"
                        + format_kg("definition_and_explanation", kg, phenomenon)
                        + "\n</Relevant Knowledge Components>"
                    )

        if current_state == "scienceqa" and child_question_level is not None:
            state_prompt = format_prompt(
                state_prompt, phenomenon, messages, child_question_level
            )
        else:
            state_prompt = format_prompt(state_prompt, phenomenon, messages)

        user_evaluation_result = child_question_level or eval_state or current_state

        if latest_user_message:
            user_message_record = Message(
                conversation_id=conversation.id,
                role="user",
                content=latest_user_message,
                state=state,
                evaluation_result=user_evaluation_result,
                matched_knowledge_components=matched_kg if matched_kg else None,
                audio_data=user_audio_bytes,
                audio_mime_type=user_audio_mime_type,
            )
            db.add(user_message_record)
            # Commit user message immediately so it's saved even if streaming fails
            try:
                db.commit()
                print(
                    f"Saved user message for conversation {conversation_id}: {latest_user_message[:50]}..."
                )
            except Exception as commit_error:
                db.rollback()
                print(f"Error committing user message: {commit_error}")
                raise

        conversation.image_path = image_path
        conversation.phenomenon = phenomenon
        conversation.updated_at = datetime.utcnow()
        if user_evaluation_result:
            conversation.evaluation_result = user_evaluation_result
        if current_state == "close" and not conversation.finished_at:
            conversation.finished_at = datetime.utcnow()
        if current_state == "close":
            state_history.pop(conversation_id, None)
            scienceqa_history.pop(conversation_id, None)

        system_message = {"role": "system", "content": CURIO_SYSTEM_PROMPT}
        all_messages = (
            [system_message] + messages + [{"role": "user", "content": state_prompt}]
        )

        # Capture variables for use inside generate() function
        saved_child_question_level = child_question_level
        saved_matched_kg = matched_kg

        def generate():
            full_content = ""
            # Create a separate database session for saving the assistant message
            # This ensures the session is available even if the outer session is closed
            # Store conversation_id in a variable to avoid accessing detached conversation object
            saved_conversation_id = conversation_id
            db_session = SessionLocal()
            try:
                # Use streaming API
                stream = client.chat.completions.create(
                    model=OPENAI_CHAT_MODEL,
                    messages=all_messages,
                    max_tokens=OPENAI_MAX_TOKENS,
                    stream=True,
                )

                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        token = chunk.choices[0].delta.content
                        full_content += token
                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

                # Fix bold formatting for scienceqa responses
                if current_state == "scienceqa":
                    original_content = full_content
                    full_content = fix_scienceqa_bold_formatting(full_content)
                    if full_content != original_content:
                        print("Fixed bold formatting in scienceqa streaming response")
                        print(f"Original: {original_content[:100]}...")
                        print(f"Fixed: {full_content[:100]}...")

                # Determine assistant evaluation result (only in scienceqa phase)
                assistant_evaluation_result = None
                if current_state == "scienceqa" and saved_child_question_level:
                    assistant_evaluation_result = saved_child_question_level

                # Save to database using separate session
                # Use saved_conversation_id string instead of conversation.id to avoid detached instance error
                assistant_message_record = Message(
                    conversation_id=saved_conversation_id,
                    role="assistant",
                    content=full_content,
                    state=current_state,
                    evaluation_result=assistant_evaluation_result,
                    matched_knowledge_components=saved_matched_kg
                    if saved_matched_kg
                    else None,
                )
                db_session.add(assistant_message_record)
                # Commit assistant message (user message already committed above)
                try:
                    db_session.commit()
                    print(
                        f"Saved assistant message for conversation {saved_conversation_id}"
                    )
                except Exception as commit_error:
                    db_session.rollback()
                    print(
                        f"Error committing assistant message for conversation {saved_conversation_id}: {commit_error}"
                    )
                    import traceback

                    print(traceback.format_exc())
                    raise

                # Send final message
                yield f"data: {json.dumps({'type': 'done', 'response': full_content, 'next_state': current_state})}\n\n"
            except Exception as e:
                db_session.rollback()
                print(f"Streaming error: {e}")
                import traceback

                print(traceback.format_exc())
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
            finally:
                db_session.close()

        return Response(stream_with_context(generate()), mimetype="text/event-stream")

    except Exception as e:
        db.rollback()
        print(f"Chat completion stream error: {e}")
        error_message = str(e)

        def error_generate():
            yield f"data: {json.dumps({'type': 'error', 'error': error_message})}\n\n"

        return Response(
            stream_with_context(error_generate()), mimetype="text/event-stream"
        )
    finally:
        if db:
            db.close()


@app.route("/api/conversations", methods=["GET"])
def get_conversations():
    """Get all conversations for a session or authenticated user"""
    db = SessionLocal()
    try:
        # Try to get user info from JWT first
        user_info = get_user_from_request(request)
        session_id = request.args.get("session_id")

        if user_info and user_info.get("userId"):
            user_id = user_info["userId"]
            print(f"Looking for conversations with user_id: {user_id}")
            conversations = (
                db.query(Conversation)
                .filter(Conversation.user_id == user_id)
                .order_by(Conversation.updated_at.desc())
                .all()
            )
            print(f"Found {len(conversations)} conversations for user_id: {user_id}")
        else:
            if not session_id:
                return jsonify(
                    {"error": "session_id is required or user must be authenticated"}
                ), 400

            print(f"Looking for conversations with session_id: {session_id}")
            conversations = (
                db.query(Conversation)
                .filter(Conversation.session_id == session_id)
                .order_by(Conversation.updated_at.desc())
                .all()
            )
            print(
                f"Found {len(conversations)} conversations for session_id: {session_id}"
            )

        # Debug: Check all conversations to see what session_ids exist
        all_convs = db.query(Conversation).limit(10).all()
        if all_convs:
            print("Sample of all conversations (first 10):")
            for conv in all_convs:
                print(
                    f"  Conversation {conv.id}: session_id={conv.session_id}, image_path={conv.image_path}"
                )

        result = []
        for conv in conversations:
            result.append(
                {
                    "id": conv.id,
                    "session_id": conv.session_id,
                    "user_id": conv.user_id,
                    "user_email": conv.user_email,
                    "username": conv.username,
                    "image_path": conv.image_path,
                    "phenomenon": conv.phenomenon,
                    "started_at": conv.started_at.isoformat()
                    if conv.started_at
                    else None,
                    "finished_at": conv.finished_at.isoformat()
                    if conv.finished_at
                    else None,
                    "updated_at": conv.updated_at.isoformat()
                    if conv.updated_at
                    else None,
                    "message_count": len(conv.messages),
                }
            )

        return jsonify({"conversations": result}), 200

    except Exception as e:
        print(f"Error getting conversations: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": "Failed to get conversations"}), 500
    finally:
        db.close()


@app.route("/api/conversations/<conversation_id>/messages", methods=["GET"])
def get_conversation_messages(conversation_id):
    """Get all messages for a conversation"""
    db = SessionLocal()
    try:
        conversation = db.get(Conversation, conversation_id)
        if not conversation:
            return jsonify({"error": "Conversation not found"}), 404

        messages = (
            db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .all()
        )

        result = []
        state_history_list = []
        scienceqa_history_list = []

        for msg in messages:
            result.append(
                {
                    "role": msg.role,
                    "content": msg.content,
                    "state": msg.state,
                    "evaluation_result": msg.evaluation_result,
                    "created_at": msg.created_at.isoformat()
                    if msg.created_at
                    else None,
                }
            )

            # Reconstruct state history from assistant messages
            if msg.role == "assistant" and msg.state:
                if (
                    msg.state not in state_history_list
                    or state_history_list[-1] != msg.state
                ):
                    state_history_list.append(msg.state)

            # Reconstruct scienceqa history from evaluation results
            if msg.evaluation_result and msg.evaluation_result in [
                "no_question",
                "irrelevant",
                "factual",
                "explanatory",
                "general_causal",
                "specific_causal",
            ]:
                scienceqa_history_list.append(msg.evaluation_result)

        # Restore state history in memory for this conversation
        state_history[conversation_id] = state_history_list
        scienceqa_history[conversation_id] = scienceqa_history_list

        return jsonify(
            {
                "conversation_id": conversation_id,
                "session_id": conversation.session_id,
                "image_path": conversation.image_path,
                "phenomenon": conversation.phenomenon,
                "messages": result,
                "state_history": state_history_list,
                "scienceqa_history": scienceqa_history_list,
            }
        ), 200

    except Exception as e:
        print(f"Error getting messages: {e}")
        return jsonify({"error": "Failed to get messages"}), 500
    finally:
        db.close()


@app.route("/api/conversations", methods=["POST"])
def create_conversation():
    """Create a new conversation"""
    db = SessionLocal()
    try:
        # Extract user info from JWT (if available)
        user_info = get_user_from_request(request)

        data = request.get_json()
        conversation_id = data.get("id") or str(uuid.uuid4())
        session_id = data.get("session_id")
        image_path = data.get("image_path", "")

        if not session_id:
            return jsonify({"error": "session_id is required"}), 400

        # Check if conversation already exists - use query instead of db.get() to avoid cache issues
        existing = (
            db.query(Conversation).filter(Conversation.id == conversation_id).first()
        )
        if existing:
            return jsonify(
                {
                    "id": existing.id,
                    "session_id": existing.session_id,
                    "image_path": existing.image_path,
                    "phenomenon": existing.phenomenon,
                    "created_at": existing.started_at.isoformat()
                    if existing.started_at
                    else None,
                }
            ), 200

        # Determine the phenomenon based on image path
        if "balloon.jpg" in image_path:
            phenomenon = "balloon"
        elif "bend.jpg" in image_path:
            phenomenon = "bend"
        elif "pepper.jpg" in image_path:
            phenomenon = "pepper"
        else:
            phenomenon = "balloon"  # default fallback

        # Prepare user info for database (optional, only if token is present)
        user_groups_json = None
        if user_info and user_info.get("groups"):
            try:
                user_groups_json = json.dumps(user_info["groups"])
            except (TypeError, ValueError):
                user_groups_json = None

        conversation = Conversation(
            id=conversation_id,
            session_id=session_id,
            image_path=image_path,
            phenomenon=phenomenon,
            user_id=user_info.get("userId") if user_info else None,
            user_email=user_info.get("email") if user_info else None,
            username=user_info.get("username") if user_info else None,
            user_groups=user_groups_json,
            started_at=datetime.utcnow(),
        )
        db.add(conversation)
        db.flush()  # Flush to ensure the conversation is in the database
        db.commit()
        db.refresh(conversation)  # Refresh to ensure we have the latest state

        return jsonify(
            {
                "id": conversation.id,
                "session_id": conversation.session_id,
                "image_path": conversation.image_path,
                "phenomenon": conversation.phenomenon,
                "created_at": conversation.started_at.isoformat()
                if conversation.started_at
                else None,
            }
        ), 201

    except Exception as e:
        db.rollback()
        print(f"Error creating conversation: {e}")
        import traceback

        print(traceback.print_exc())
        return jsonify({"error": "Failed to create conversation"}), 500
    finally:
        db.close()


@app.route("/api/conversations/<conversation_id>/messages", methods=["POST"])
def create_message(conversation_id):
    """Create a new message in a conversation"""
    db = SessionLocal()
    try:
        # Use query instead of db.get() to explicitly query the database and avoid cache issues
        conversation = (
            db.query(Conversation).filter(Conversation.id == conversation_id).first()
        )
        if not conversation:
            # Log for debugging
            print(
                f"Conversation {conversation_id} not found when trying to create message"
            )
            # Check if conversation exists at all (for debugging)
            all_conv_ids = [str(c.id) for c in db.query(Conversation.id).all()]
            print(
                f"Available conversation IDs: {all_conv_ids[:5]}..."
            )  # Print first 5 for debugging
            return jsonify({"error": "Conversation not found"}), 404

        data = request.get_json()
        role = data.get("role")
        content = data.get("content")
        state = data.get("state", "greet")

        if not role or not content:
            return jsonify({"error": "role and content are required"}), 400

        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            state=state,
        )
        db.add(message)
        db.commit()

        return jsonify(
            {
                "id": message.id,
                "role": message.role,
                "content": message.content,
                "state": message.state,
                "created_at": message.created_at.isoformat()
                if message.created_at
                else None,
            }
        ), 201

    except Exception as e:
        db.rollback()
        print(f"Error creating message: {e}")
        import traceback

        print(traceback.format_exc())
        return jsonify({"error": "Failed to create message"}), 500
    finally:
        db.close()


@app.route("/api/conversations/<conversation_id>", methods=["GET"])
def get_conversation(conversation_id):
    """Get a specific conversation with its latest state"""
    db = SessionLocal()
    try:
        conversation = db.get(Conversation, conversation_id)
        if not conversation:
            return jsonify({"error": "Conversation not found"}), 404

        # Get the last message to determine current state
        last_message = (
            db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .first()
        )

        current_state = last_message.state if last_message else "greet"

        return jsonify(
            {
                "id": conversation.id,
                "session_id": conversation.session_id,
                "image_path": conversation.image_path,
                "phenomenon": conversation.phenomenon,
                "current_state": current_state,
                "started_at": conversation.started_at.isoformat()
                if conversation.started_at
                else None,
                "finished_at": conversation.finished_at.isoformat()
                if conversation.finished_at
                else None,
                "updated_at": conversation.updated_at.isoformat()
                if conversation.updated_at
                else None,
            }
        ), 200

    except Exception as e:
        print(f"Error getting conversation: {e}")
        return jsonify({"error": "Failed to get conversation"}), 500
    finally:
        db.close()


@app.route("/api/speech", methods=["POST"])
def generate_speech():
    """Generate speech audio using OpenAI TTS"""
    try:
        # Calculate latency from conversation start to audio generation
        session_id = request.remote_addr
        end_time = time.time()

        if session_id in conversation_start_times:
            total_latency = end_time - conversation_start_times[session_id]
            print(
                f"🎯 Total latency (user message → audio response): {total_latency:.2f} seconds"
            )
            # Clean up the stored start time
            del conversation_start_times[session_id]
        else:
            print("⚠️  No start time found for session, cannot calculate latency")

        data = request.get_json()
        text = data.get("text", "")

        if not text:
            return jsonify({"error": "No text provided"}), 400

        # Clean markdown formatting from text for TTS
        # This removes ** markers that can cause TTS to break
        # The original text with markdown is preserved in the database/display
        cleaned_text = clean_text_for_speech(text)

        # Generate speech using OpenAI TTS
        response = client.audio.speech.create(
            model=OPENAI_TTS_MODEL,
            voice=OPENAI_TTS_VOICE,
            input=cleaned_text,
            response_format="mp3",
        )

        # Return the audio data
        return (
            response.content,
            200,
            {
                "Content-Type": "audio/mpeg",
                "Content-Disposition": "attachment; filename=speech.mp3",
            },
        )

    except Exception as e:
        print(f"Speech generation error: {e}")
        return jsonify({"error": "Speech generation failed"}), 500


# Register database viewer blueprint
from database_viewer import db_viewer, init_db_viewer  # noqa: E402

init_db_viewer(SessionLocal, Conversation, Message)
app.register_blueprint(db_viewer)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5001))  # Default 5001 for local dev
    debug = os.getenv("FLASK_ENV", "development") == "development"
    app.run(debug=debug, host="0.0.0.0", port=port)
