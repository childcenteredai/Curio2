import base64
import io
import json
import os
import re
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
from prompts.eval import scaffolding, scienceqa
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
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-2025-04-14")
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

# App version: 1 = bubbles on match only; 2 = all bubbles visible (gray), light up on match
CURIO_APP_VERSION = int(os.getenv("CURIO_APP_VERSION", "1"))

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
matched_concepts_history = defaultdict(
    list
)  # Track matched concepts for each conversation
scienceqa_turn_count = defaultdict(int)  # Track number of scienceqa turns
all_concepts_matched_flag = defaultdict(
    bool
)  # Flag to indicate if all concepts have been matched
scienceqa_turn_count = defaultdict(int)  # Track number of scienceqa turns


def state_classification(state, messages, phenomenon):
    # Load prompt from the txt file
    if state in ["greet", "scaffolding"]:
        eval_prompt = format_prompt(scaffolding, phenomenon, messages)
    elif state in ["discover", "scienceqa"]:
        eval_prompt = format_prompt(scienceqa, phenomenon, messages)
    else:
        # Unknown state: default to scienceqa evaluator
        eval_prompt = format_prompt(scienceqa, phenomenon, messages)

    messages = [{"role": "system", "content": eval_prompt}]
    # print(f"messages: {messages}")

    response = client.chat.completions.create(
        model=OPENAI_CHAT_MODEL,
        messages=messages,
        max_tokens=OPENAI_MAX_TOKENS,
        temperature=1.0,
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
    next_state = eval_state
    if eval_state == "discover":
        next_state = "discover"
    elif eval_state == "scienceqa":
        if len(state_history_list) > 0 and state_history_list[-1] == "scaffolding":
            next_state = "discover"
        else:
            # Closing should be driven by knowledge-component completion logic.
            next_state = "scienceqa"
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
        else:
            # If child_question_level is None or unknown, this should not happen
            # as state_classification should always be called first
            # Use level_0 as fallback
            print(
                f"WARNING: state_prompt_classification called for scienceqa with child_question_level={child_question_level}, using level_0 as fallback"
            )
            return level_0
    elif state == "close":
        return open("prompts/close.txt", "r").read()
    else:
        # Unknown state, use level_0 as fallback
        print(
            f"WARNING: state_prompt_classification called with unknown state={state}, using level_0 as fallback"
        )
        return level_0


def format_prompt(
    state_prompt,
    phenomenon="balloon",
    messages=None,
    child_question_level=None,
    first_time_matched_concepts=None,
    app_version=None,
):
    if messages is None:
        messages = []

    # Check if state_prompt is None or empty
    if not state_prompt or not isinstance(state_prompt, str):
        print(
            f"WARNING: state_prompt is None or invalid in format_prompt: {state_prompt}"
        )
        return "Respond to the child's question."

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
            "balloon": "Hair Stands Up Near a Balloon",
            "bend": "Bending Water Stream with a Comb",
            "pepper": "Pepper Leaping up to Spoon",
        }
        phenomenon_key = phenomenon_map.get(phenomenon, "Hair Stands Up Near a Balloon")
        mechanism = knowledge_base.get(phenomenon_key, {}).get("mechanism", "")
        state_prompt = state_prompt.replace(
            "<Mechanism Context>",
            "<Mechanism Context>\n" + mechanism,
        )

    if "{kg_concepts}" in state_prompt:
        # Load knowledge base and extract all concepts and sub-concepts
        knowledge_base = json.load(open("knowledge/kg.json", "r"))
        phenomenon_map = {
            "balloon": "Hair Stands Up Near a Balloon",
            "bend": "Bending Water Stream with a Comb",
            "pepper": "Pepper Leaping up to Spoon",
        }
        phenomenon_key = phenomenon_map.get(phenomenon, "Hair Stands Up Near a Balloon")
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

    # Version 2: clues hint for discover prompt
    if "{clues_hint}" in state_prompt:
        effective_version = (
            app_version if app_version is not None else CURIO_APP_VERSION
        )
        if effective_version == 2:
            knowledge_base = json.load(open("knowledge/kg.json", "r"))
            phenomenon_map = {
                "balloon": "Hair Stands Up Near a Balloon",
                "bend": "Bending Water Stream with a Comb",
                "pepper": "Pepper Leaping up to Spoon",
            }
            phenomenon_key = phenomenon_map.get(
                phenomenon, "Hair Stands Up Near a Balloon"
            )
            concepts_dict = knowledge_base.get(phenomenon_key, {}).get("concepts", {})
            num_clues = len(concepts_dict) if concepts_dict else 8
            state_prompt = state_prompt.replace(
                "{clues_hint}",
                f"See! There are **{num_clues}** **clues** **in** **bubbles** 🫧 waiting for you to discover to solve this mystery! ",
            )
        else:
            state_prompt = state_prompt.replace("{clues_hint}", "")

    # Scienceqa levels > 1: add "You just spotted one clue!" when new concept matched
    if "{clue_spotted_hint}" in state_prompt:
        levels_with_hint = ("explanatory", "general_causal", "specific_causal")
        if (
            child_question_level in levels_with_hint
            and first_time_matched_concepts
            and len(first_time_matched_concepts) > 0
        ):
            state_prompt = state_prompt.replace(
                "{clue_spotted_hint}", " You just spotted one clue in the bubbles 🫧!"
            )
        else:
            state_prompt = state_prompt.replace("{clue_spotted_hint}", "")

    return state_prompt


def build_structured_kg(concepts_dict):
    """
    Build a structured knowledge graph showing concept/sub-concept hierarchy.
    Each concept node includes its `definition` (when available).
    Returns a dictionary with concepts and their sub-concepts.
    """
    structured_kg = {}
    for concept_name, concept_data in concepts_dict.items():
        definition = (
            concept_data.get("definition", "") if isinstance(concept_data, dict) else ""
        )
        structured_kg[concept_name] = {"definition": definition}
        if (
            isinstance(concept_data, dict)
            and "sub_concepts" in concept_data
            and concept_data["sub_concepts"]
        ):
            sub_concepts_list = []
            for sub_concept_name, sub_concept_data in concept_data[
                "sub_concepts"
            ].items():
                sub_definition = (
                    sub_concept_data.get("definition", "")
                    if isinstance(sub_concept_data, dict)
                    else ""
                )
                sub_concept_entry = {
                    "name": sub_concept_name,
                    "definition": sub_definition,
                }
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


def parse_matched_kg_and_record_first_time(
    matched_kg, phenomenon, conversation_id, matched_concepts_history
):
    """
    Parse matched_kg (from knowledge_retrieval), add to matched_concepts_history if new.
    Returns list of concept names that were first-time matches (for concept bubbles).
    """
    first_time = []
    if not matched_kg or matched_kg == "":
        return first_time
    knowledge_base = json.load(open("knowledge/kg.json", "r"))
    phenomenon_map = {
        "balloon": "Hair Stands Up Near a Balloon",
        "bend": "Bending Water Stream with a Comb",
        "pepper": "Pepper Leaping up to Spoon",
    }
    phenomenon_key = phenomenon_map.get(phenomenon, "Hair Stands Up Near a Balloon")
    concept_names = list(
        knowledge_base.get(phenomenon_key, {}).get("concepts", {}).keys()
    )
    try:
        kg_list = (
            json.loads(matched_kg)
            if isinstance(matched_kg, str) and matched_kg.startswith("[")
            else json.loads(f'["{matched_kg}"]')
            if isinstance(matched_kg, str)
            else matched_kg
        )
        if isinstance(kg_list, list) and len(kg_list) > 0:
            matched_concept_raw = kg_list[0]
            for cn in concept_names:
                if cn.lower() == matched_concept_raw.lower():
                    matched_concepts_ref = matched_concepts_history[conversation_id]
                    if cn not in matched_concepts_ref:
                        matched_concepts_ref.append(cn)
                        first_time.append(cn)
                        print(f"[Concept Logic] First-time match: {cn}")
                    break
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass
    return first_time


def get_matched_concepts_from_db(
    conversation_id, phenomenon="balloon", db_session=None
):
    """
    Extract all matched concepts from database conversation history.
    These are concepts that were matched for EXPLANATION purposes.
    Returns a list of concept names that have been matched in previous turns, in order.
    """
    matched_concepts = []

    if not db_session:
        return matched_concepts

    # Load knowledge base to get concept names
    knowledge_base = open("knowledge/kg.json", "r").read()
    knowledge_base = json.loads(knowledge_base)

    phenomenon_map = {
        "balloon": "Hair Stands Up Near a Balloon",
        "bend": "Bending Water Stream with a Comb",
        "pepper": "Pepper Leaping up to Spoon",
    }
    phenomenon_key = phenomenon_map.get(phenomenon, "Hair Stands Up Near a Balloon")
    concepts_dict = knowledge_base.get(phenomenon_key, {}).get("concepts", {})
    concept_names = list(concepts_dict.keys())

    # Query database for assistant messages with matched knowledge components
    assistant_messages = (
        db_session.query(Message)
        .filter(
            Message.conversation_id == conversation_id,
            Message.role == "assistant",
            Message.matched_knowledge_components.isnot(None),
        )
        .order_by(Message.created_at.asc())
        .all()
    )

    # Extract matched concepts in order
    for msg in assistant_messages:
        matched_kg = msg.matched_knowledge_components
        if matched_kg:
            try:
                # Try to parse as JSON list
                kg_list = (
                    json.loads(matched_kg)
                    if isinstance(matched_kg, str)
                    else matched_kg
                )
                if isinstance(kg_list, list) and len(kg_list) > 0:
                    concept_name = kg_list[0]
                    # Normalize the concept name (case-insensitive match)
                    for cn in concept_names:
                        if cn.lower() == concept_name.lower():
                            if cn not in matched_concepts:
                                matched_concepts.append(cn)
                            break
            except (json.JSONDecodeError, TypeError):
                # If not JSON, try direct string match
                matched_kg_str = str(matched_kg).lower()
                for cn in concept_names:
                    if cn.lower() == matched_kg_str:
                        if cn not in matched_concepts:
                            matched_concepts.append(cn)
                        break

    return matched_concepts


def get_next_concept_for_prompting(
    conversation_id, phenomenon="balloon", db_session=None
):
    """
    Get the next concept to use for prompting question.
    Uses an index pointer mechanism: count existing scienceqa assistant messages to determine
    the current index, then return the concept at that index.

    Returns the concept name (string) or None if all concepts have been used.
    """
    if not db_session:
        return None

    # Load knowledge base
    knowledge_base = open("knowledge/kg.json", "r").read()
    knowledge_base = json.loads(knowledge_base)

    phenomenon_map = {
        "balloon": "Hair Stands Up Near a Balloon",
        "bend": "Bending Water Stream with a Comb",
        "pepper": "Pepper Leaping up to Spoon",
    }
    phenomenon_key = phenomenon_map.get(phenomenon, "Hair Stands Up Near a Balloon")
    concepts_dict = knowledge_base.get(phenomenon_key, {}).get("concepts", {})
    concept_names = list(concepts_dict.keys())

    if not concept_names:
        return None

    # Calculate current index: count existing scienceqa assistant messages
    # Each scienceqa turn uses one concept for prompting question in sequential order
    # The index points to the next concept to use
    assistant_messages = (
        db_session.query(Message)
        .filter(
            Message.conversation_id == conversation_id,
            Message.role == "assistant",
            Message.state == "scienceqa",
        )
        .order_by(Message.created_at.asc())
        .all()
    )

    # Current index = number of scienceqa turns (concepts[0..index-1] have been used)
    current_index = len(assistant_messages)
    # Check if we've used all concepts
    if current_index >= len(concept_names):
        print(
            f"[Prompting Question] All concepts used. Index: {current_index}, Total: {len(concept_names)}"
        )
        return None

    # Return the concept at current index
    next_concept = concept_names[current_index]
    print(
        f"[Prompting Question] Current index: {current_index}, Next concept: {next_concept}"
    )
    return next_concept


def knowledge_retrieval(
    messages, phenomenon="balloon", conversation_id=None, db_session=None
):
    """
    When a child asks a question, match the most relevant knowledge component (concept)
    from the knowledge base that can explain the question.

    Returns:
        - A JSON string representing the matched concept (e.g., '["Force at a Distance"]')
        - Empty string ('') if no suitable component can be matched
        - None if there's an error

    This function is ONLY responsible for matching concepts for EXPLANATION purposes.
    It does NOT handle prompting questions.
    """
    # Load prompt from the txt file
    retrieval_prompt = open("prompts/knowledge_matching.txt", "r").read()
    retrieval_prompt = format_prompt(retrieval_prompt, phenomenon, messages)
    matched_so_far = []
    if conversation_id is not None:
        matched_so_far = list(matched_concepts_history[conversation_id])
    matched_concepts_text = (
        json.dumps(matched_so_far, ensure_ascii=False)
        if matched_so_far
        else "[]  (no concepts matched earlier in this conversation)"
    )
    if "<Matched Concepts>" in retrieval_prompt:
        retrieval_prompt = retrieval_prompt.replace(
            "<Matched Concepts>",
            "<Matched Concepts>\n" + matched_concepts_text,
        )
    knowledge_base = open("knowledge/kg.json", "r").read()
    knowledge_base = json.loads(knowledge_base)

    # Map phenomenon to knowledge base key
    phenomenon_map = {
        "balloon": "Hair Stands Up Near a Balloon",
        "bend": "Bending Water Stream with a Comb",
        "pepper": "Pepper Leaping up to Spoon",
    }
    phenomenon_key = phenomenon_map.get(phenomenon, "Hair Stands Up Near a Balloon")

    # Verify the phenomenon exists in the knowledge base
    if phenomenon_key not in knowledge_base:
        print(f"Warning: Phenomenon '{phenomenon_key}' not found in knowledge base")
        return None

    # Build structured KG with concept/sub-concept hierarchy
    concepts_dict = knowledge_base.get(phenomenon_key, {}).get("concepts", {})
    if not concepts_dict:
        print(f"Warning: No concepts found for phenomenon '{phenomenon_key}'")
        return None

    # Get the ordered list of concepts (maintain order from JSON)
    concept_names = list(concepts_dict.keys())

    structured_kg = build_structured_kg(concepts_dict)

    # Calculate conversation turn count (each user message + assistant response = 1 turn)
    # Count user messages as turns
    turn_count = sum(1 for msg in messages if msg.get("role") == "user")

    # Add structured KG information to the prompt
    retrieval_prompt = (
        retrieval_prompt
        + "\n\n<Knowledge Graph>\n"
        + json.dumps(structured_kg, indent=2)
        + "\n</Knowledge Graph>"
        + f"\n\n<Conversation Turn Count>\nCurrent turn: {turn_count}\n</Conversation Turn Count>"
    )

    # print(f"retrieval_prompt: {retrieval_prompt}")
    messages_for_llm = [{"role": "system", "content": retrieval_prompt}]
    response = client.chat.completions.create(
        model=OPENAI_CHAT_MODEL,
        messages=messages_for_llm,
        max_tokens=OPENAI_MAX_TOKENS,
        temperature=1.0,
    )

    # content = response.output_text or ""
    content = response.choices[0].message.content or ""
    kg_raw = content.strip()

    # Validate the matched concept exists in the knowledge base
    if kg_raw:
        # New format: JSON dict with matched_concept + relevancy_score
        parsed = None
        try:
            # Be tolerant of surrounding text/code fences: extract the first JSON object.
            start = kg_raw.find("{")
            end = kg_raw.rfind("}")
            candidate = kg_raw
            if start != -1 and end != -1 and end > start:
                candidate = kg_raw[start : end + 1]
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            parsed = None

        if isinstance(parsed, dict):
            matched_concept = (
                parsed.get("matched_concept")
                or parsed.get("matchedConcept")
                or parsed.get("concept")
                or ""
            )
            relevancy_score = (
                parsed.get("relevancy_score")
                or parsed.get("relevancyScore")
                or parsed.get("score")
                or 0
            )
            try:
                relevancy_score_float = float(relevancy_score)
            except (TypeError, ValueError):
                relevancy_score_float = 0.0

            # Log for debugging; decision is based on score threshold.
            print(
                f"[Knowledge Retrieval] Model relevancy_score={relevancy_score_float}, matched_concept={matched_concept!r}"
            )

            if matched_concept and relevancy_score_float >= 0.5:
                # Normalize and check if it exists in knowledge base
                matched_concept_normalized = None
                for cn in concept_names:
                    if cn.lower() == str(matched_concept).lower():
                        matched_concept_normalized = cn
                        break

                if matched_concept_normalized:
                    # Valid match, return the normalized concept name as JSON
                    return json.dumps([matched_concept_normalized])

                # Concept not found in knowledge base
                print(
                    f"Warning: Matched concept '{matched_concept}' not found in knowledge base"
                )
                return ""

            # If relevancy_score < 0.5, don't adopt the matched concept.
            return ""

        # Backward-compatible fallback: old format (JSON list or raw string)
        try:
            kg_list = (
                json.loads(kg_raw)
                if kg_raw.startswith("[")
                else json.loads(f'["{kg_raw}"]')
            )
            if isinstance(kg_list, list) and len(kg_list) > 0:
                matched_concept = kg_list[0]
                matched_concept_normalized = None
                for cn in concept_names:
                    if cn.lower() == str(matched_concept).lower():
                        matched_concept_normalized = cn
                        break

                if matched_concept_normalized:
                    return json.dumps([matched_concept_normalized])
                else:
                    print(
                        f"Warning: Matched concept '{matched_concept}' not found in knowledge base"
                    )
                    return ""
        except (json.JSONDecodeError, TypeError) as e:
            matched_concept_normalized = None
            for cn in concept_names:
                if cn.lower() == kg_raw.lower():
                    matched_concept_normalized = cn
                    break

            if matched_concept_normalized:
                return json.dumps([matched_concept_normalized])
            else:
                print(f"Warning: Could not parse or match concept from '{kg_raw}': {e}")
                return ""

    # No match found or empty response
    print("No knowledge component matched for this question")
    return ""


def extract_kg_definition_and_explanation(kg_raw, phenomenon="balloon"):
    """
    Extract definition and explanation from a matched knowledge component.
    Returns a tuple (definition, explanation) or (None, None) if not found.
    """
    if not kg_raw or kg_raw == "":
        return None, None

    knowledge_base = open("knowledge/kg.json", "r").read()
    knowledge_base = json.loads(knowledge_base)

    # Map phenomenon to knowledge base key
    phenomenon_map = {
        "balloon": "Hair Stands Up Near a Balloon",
        "bend": "Bending Water Stream with a Comb",
        "pepper": "Pepper Leaping up to Spoon",
    }
    phenomenon_key = phenomenon_map.get(phenomenon, "Hair Stands Up Near a Balloon")

    if phenomenon_key not in knowledge_base:
        return None, None

    if "concepts" not in knowledge_base[phenomenon_key]:
        return None, None

    try:
        kg_list = json.loads(kg_raw) if isinstance(kg_raw, str) else kg_raw

        if not kg_list or len(kg_list) == 0:
            return None, None

        component = kg_list[0]

        # Get the actual concept key (case-insensitive matching)
        concepts = knowledge_base[phenomenon_key]["concepts"]
        actual_component_key = None

        if component in concepts:
            actual_component_key = component
        else:
            component_lower = component.lower()
            for key in concepts.keys():
                if key.lower() == component_lower:
                    actual_component_key = key
                    break

        if actual_component_key is None:
            return None, None

        # Get the component data
        component_data = concepts[actual_component_key]
        definition = component_data.get("definition", "")
        explanation = component_data.get("explanation", "")

        return definition, explanation
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"Error extracting knowledge component: {e}")
        return None, None


def get_explanation_method_and_matched_kg(
    child_question_level,
    messages,
    phenomenon,
    conversation_id,
    db_session,
    log_prefix="[Knowledge Retrieval]",
    run_for_any_question=False,
):
    """
    Shared helper for scienceqa:
    - Optionally run knowledge retrieval for EXPLANATION depending on question level
    - Build explanation_method string for {explanation_method} placeholder

    Returns:
        (matched_kg, explanation_method)
    """
    explanation_method = (
        "No strongly matched knowledge component is available for this turn. "
        "Use the child's latest message and conversation history to respond naturally "
        "and guide exploration, without directly revealing the phenomenon or introducing "
        "any specific matched concept."
    )
    matched_kg = None

    if run_for_any_question:
        if child_question_level == "no_question":
            return matched_kg, explanation_method
    else:
        if child_question_level not in [
            "factual",
            "explanatory",
            "general_causal",
            "specific_causal",
        ]:
            return matched_kg, explanation_method

    kg = knowledge_retrieval(messages, phenomenon, conversation_id, db_session)
    matched_kg = kg if kg else None
    print(
        f"{log_prefix} Matched component for explanation: {matched_kg if matched_kg else 'None'}"
    )

    definition = ""
    explanation = ""
    if matched_kg and matched_kg != "":
        definition, explanation = extract_kg_definition_and_explanation(
            matched_kg, phenomenon
        )
        if definition and explanation:
            explanation_method = f"Here are the matched knowledge component's definition: {definition} and explanation: {explanation}. Based on the conversation history, use the provided knowledge component to explain the knowledge. The definition describes the formal definition of the concept, and the explanation describes how the concept works in the image. These two parts are for your reference. The explanation part of your response should be: (1) focus on the provided knowledge component and avoid introducing other concepts to confuse the child (e.g., if you are introducing 'electrons', do not mention 'charge'), (2) naturally flowing from the conversation history, and (3) must be within 30 words."

    return matched_kg, explanation_method


def format_kg(mode="definition", kg_raw="", phenomenon="balloon"):
    """
    Format a knowledge component for use in prompts.
    This is used for EXPLANATION purposes only.
    """
    knowledge_base = open("knowledge/kg.json", "r").read()
    knowledge_base = json.loads(knowledge_base)

    # Map phenomenon to knowledge base key
    phenomenon_map = {
        "balloon": "Hair Stands Up Near a Balloon",
        "bend": "Bending Water Stream with a Comb",
        "pepper": "Pepper Leaping up to Spoon",
    }
    phenomenon_key = phenomenon_map.get(phenomenon, "Hair Stands Up Near a Balloon")

    # Verify the phenomenon exists in the knowledge base
    if phenomenon_key not in knowledge_base:
        print(f"Warning: Phenomenon '{phenomenon_key}' not found in knowledge base")
        return ""

    if "concepts" not in knowledge_base[phenomenon_key]:
        print(f"Warning: No concepts found for phenomenon '{phenomenon_key}'")
        return ""

    try:
        kg_list = json.loads(kg_raw) if isinstance(kg_raw, str) else kg_raw

        # Only use the FIRST component (most relevant one)
        # Do not process multiple components
        if not kg_list or len(kg_list) == 0:
            return ""

        component = kg_list[0]  # Take only the first component

        # Get the actual concept key (case-insensitive matching)
        concepts = knowledge_base[phenomenon_key]["concepts"]
        actual_component_key = None

        # First try exact match
        if component in concepts:
            actual_component_key = component
        else:
            # Try case-insensitive match
            component_lower = component.lower()
            for key in concepts.keys():
                if key.lower() == component_lower:
                    actual_component_key = key
                    break

        if actual_component_key is None:
            print(f"Warning: Component '{component}' not found in knowledge base")
            return ""

        # Get the component data (do NOT include sub_concepts)
        component_data = concepts[actual_component_key]
        definition = component_data.get("definition", "")
        explanation = component_data.get("explanation", "")

        # Format the single component (without sub_concepts)
        if mode == "definition":
            kg_content = f"'{actual_component_key}':\n\nDefinition: {definition}\n\n"
        elif mode == "explanation":
            kg_content = f"'{actual_component_key}':\n\nExplanation: {explanation}\n\n"
        elif mode == "definition_and_explanation":
            kg_content = f"'{actual_component_key}':\n\nDefinition: {definition}\n\nExplanation: {explanation}\n\n"
        else:
            kg_content = ""

        kg_content = kg_content.strip()
        print(f"kg_content (for explanation): {kg_content}")
        return kg_content
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"Error processing knowledge graph: {e}")
        return ""


def format_concept_for_prompting(concept_name, phenomenon="balloon"):
    """
    Format a concept for use in prompting questions.
    This is used for PROMPTING QUESTION purposes only.
    Returns the concept's definition (not explanation) to guide question generation.
    """
    if not concept_name:
        return ""

    knowledge_base = open("knowledge/kg.json", "r").read()
    knowledge_base = json.loads(knowledge_base)

    # Map phenomenon to knowledge base key
    phenomenon_map = {
        "balloon": "Hair Stands Up Near a Balloon",
        "bend": "Bending Water Stream with a Comb",
        "pepper": "Pepper Leaping up to Spoon",
    }
    phenomenon_key = phenomenon_map.get(phenomenon, "Hair Stands Up Near a Balloon")

    # Verify the phenomenon exists in the knowledge base
    if phenomenon_key not in knowledge_base:
        print(f"Warning: Phenomenon '{phenomenon_key}' not found in knowledge base")
        return ""

    if "concepts" not in knowledge_base[phenomenon_key]:
        print(f"Warning: No concepts found for phenomenon '{phenomenon_key}'")
        return ""

    concepts = knowledge_base[phenomenon_key]["concepts"]

    # Find the concept (case-insensitive)
    actual_concept_key = None
    if concept_name in concepts:
        actual_concept_key = concept_name
    else:
        concept_name_lower = concept_name.lower()
        for key in concepts.keys():
            if key.lower() == concept_name_lower:
                actual_concept_key = key
                break

    if actual_concept_key is None:
        print(f"Warning: Concept '{concept_name}' not found in knowledge base")
        return ""

    # Get only the definition (not explanation) for prompting questions
    concept_data = concepts[actual_concept_key]
    definition = concept_data.get("definition", "")

    # Format for prompting question guidance
    concept_content = f"'{actual_concept_key}':\n\nDefinition: {definition}\n\n"
    concept_content = concept_content.strip()
    print(f"concept_content (for prompting question): {concept_content}")
    return concept_content


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


@app.route("/api/config", methods=["GET"])
def get_config():
    """Return app config (e.g. curio_app_version for frontend)"""
    return jsonify({"curio_app_version": CURIO_APP_VERSION})


@app.route("/api/knowledge/concepts", methods=["GET"])
def get_concept_explanations():
    """Return concept explanations for a phenomenon (for bubble hover tooltips)"""
    phenomenon = request.args.get("phenomenon", "balloon")
    phenomenon_map = {
        "balloon": "Hair Stands Up Near a Balloon",
        "bend": "Bending Water Stream with a Comb",
        "pepper": "Pepper Leaping up to Spoon",
        "salt": "Pepper Leaping up to Spoon",
    }
    phenomenon_key = phenomenon_map.get(phenomenon, "Hair Stands Up Near a Balloon")
    knowledge_base = json.load(open("knowledge/kg.json", "r"))
    concepts = knowledge_base.get(phenomenon_key, {}).get("concepts", {})
    result = {
        name: {
            "explanation": data.get("explanation", ""),
            "definition": data.get("definition", ""),
        }
        for name, data in concepts.items()
    }
    return jsonify(result)


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
        curio_app_version = data.get("curio_app_version")
        try:
            app_version = (
                int(curio_app_version) if curio_app_version is not None else None
            )
        except (TypeError, ValueError):
            app_version = None

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

        # Reconstruct conversation history from database for existing conversations
        if conversation.created_at:
            (
                loaded_state_history,
                loaded_scienceqa_history,
                loaded_matched_concepts,
            ) = get_conversation_history_for_chat(conversation_id, db, phenomenon)
            state_history[conversation_id] = loaded_state_history
            scienceqa_history[conversation_id] = loaded_scienceqa_history
            matched_concepts_history[conversation_id] = loaded_matched_concepts

            # Reflection stage removed: count all scienceqa turns
            scienceqa_turn_count[conversation_id] = loaded_state_history.count(
                "scienceqa"
            )

            knowledge_base = json.load(open("knowledge/kg.json", "r"))
            phenomenon_map = {
                "balloon": "Hair Stands Up Near a Balloon",
                "bend": "Bending Water Stream with a Comb",
                "pepper": "Pepper Leaping up to Spoon",
            }
            phenomenon_key = phenomenon_map.get(
                phenomenon, "Hair Stands Up Near a Balloon"
            )
            concepts_dict = knowledge_base.get(phenomenon_key, {}).get("concepts", {})
            concept_names = list(concepts_dict.keys())
            all_concepts_matched_flag[conversation_id] = (
                len(loaded_matched_concepts) >= len(concept_names)
                if concept_names
                else False
            )

            print(
                f"[History Reconstruction] Loaded state: {loaded_state_history}, "
                f"scienceqa: {loaded_scienceqa_history}, "
                f"matched concepts: {loaded_matched_concepts}, "
                f"turn_count: {scienceqa_turn_count[conversation_id]}, "
                f"all_matched: {all_concepts_matched_flag[conversation_id]}"
            )

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
                    matched_knowledge_components=None,
                    next_concept=None,
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

            # If transitioning to scienceqa, reset turn count and classify question level
            if current_state == "scienceqa":
                # Reset turn count when entering scienceqa from another state
                if conv_state_history and conv_state_history[-1] != "scienceqa":
                    scienceqa_turn_count[conversation_id] = 0
                # Classify the child's question level (always use the scienceqa evaluator prompt)
                child_question_level = state_classification(
                    "scienceqa", messages, phenomenon
                )
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
            # In scienceqa state: always stay in scienceqa until all concepts are matched
            scienceqa_turn_count[conversation_id] += 1
            turn_count = scienceqa_turn_count[conversation_id]

            # Stay in scienceqa state, classify the child's question level
            child_question_level = state_classification(
                "scienceqa", messages, phenomenon
            )
            conv_scienceqa_history.append(child_question_level)
            current_state = "scienceqa"
            state_prompt = state_prompt_classification(
                current_state, child_question_level
            )
            if latest_user_message:
                print("\n=== Turn Evaluation (Non-Stream) ===")
                print(f"Child's Question: {latest_user_message}")
                print(f"Evaluation Result: {child_question_level} (turn {turn_count})")
                print("=" * 50)
            if not conv_state_history or conv_state_history[-1] != current_state:
                conv_state_history.append(current_state)
            eval_state = current_state

        # ============================================================
        # Response Generation
        # ============================================================
        # A. Knowledge Retrieval - for EXPLANATION only
        matched_kg = None  # For explanation
        next_concept_for_prompting = (
            None  # For prompting question (initialized for all states)
        )
        matched_concept = None  # Matched concept from knowledge retrieval
        first_time_matched_concepts = []  # Concepts newly matched this turn (for concept bubbles)

        if current_state == "scienceqa":
            # Load knowledge base to get concept list
            knowledge_base = open("knowledge/kg.json", "r").read()
            knowledge_base = json.loads(knowledge_base)
            phenomenon_map = {
                "balloon": "Hair Stands Up Near a Balloon",
                "bend": "Bending Water Stream with a Comb",
                "pepper": "Pepper Leaping up to Spoon",
            }
            phenomenon_key = phenomenon_map.get(
                phenomenon, "Hair Stands Up Near a Balloon"
            )
            concepts_dict = knowledge_base.get(phenomenon_key, {}).get("concepts", {})
            concept_names = list(concepts_dict.keys())

            # Get matched concepts history for this conversation
            matched_concepts = matched_concepts_history[conversation.id]

            # A. Knowledge Retrieval (EXPLANATION only) + explanation placeholder
            matched_kg, explanation_method = get_explanation_method_and_matched_kg(
                child_question_level,
                messages,
                phenomenon,
                conversation.id,
                db,
                log_prefix="[Knowledge Retrieval]",
            )

            # Parse matched concept and add to history if not already present
            if matched_kg and matched_kg != "":
                try:
                    kg_list = (
                        json.loads(matched_kg)
                        if isinstance(matched_kg, str) and matched_kg.startswith("[")
                        else json.loads(f'["{matched_kg}"]')
                        if isinstance(matched_kg, str)
                        else matched_kg
                    )
                    if isinstance(kg_list, list) and len(kg_list) > 0:
                        matched_concept_raw = kg_list[0]
                        # Normalize the concept name
                        for cn in concept_names:
                            if cn.lower() == matched_concept_raw.lower():
                                matched_concept = cn
                                # Add to matched concepts history if not already present
                                if matched_concept not in matched_concepts:
                                    matched_concepts.append(matched_concept)
                                    first_time_matched_concepts.append(matched_concept)
                                    print(
                                        f"[Concept Logic] Added to matched history: {matched_concept}"
                                    )
                                break
                except (json.JSONDecodeError, TypeError, AttributeError):
                    pass

            # Find next concept: lowest order concept that hasn't been matched
            next_concept_for_prompting = None
            for concept_name in concept_names:
                if concept_name not in matched_concepts:
                    next_concept_for_prompting = concept_name
                    break

            # If all concepts have been matched, keep scienceqa (next_concept stays empty)
            if next_concept_for_prompting is None:
                print(
                    "[Concept Logic] All concepts matched! Staying in scienceqa with empty next_concept."
                )
                all_concepts_matched_flag[conversation_id] = True

            # Replace placeholders in prompt (only if still in scienceqa state)
            if current_state == "scienceqa":
                state_prompt = state_prompt.replace(
                    "{explanation_method}", explanation_method
                )

            # Replace placeholders for all scienceqa questions
            if current_state == "scienceqa":
                # Fill in current_concept from the matched knowledge component
                if not matched_concept:
                    # If matched_concept is empty, adjust the prompt wording to avoid
                    # "current concept ()" - use "the explanation part" instead.
                    state_prompt = state_prompt.replace(
                        "the current concept ({current_concept})",
                        "the explanation part",
                    )
                    state_prompt = state_prompt.replace("{current_concept}", "")
                else:
                    state_prompt = state_prompt.replace(
                        "{current_concept}", matched_concept
                    )

                state_prompt = state_prompt.replace(
                    "{next_concept}",
                    next_concept_for_prompting if next_concept_for_prompting else "",
                )
                # Only when next_concept is empty, relax the prompting-question constraints.
                if not next_concept_for_prompting:
                    state_prompt = state_prompt.replace(
                        "- You need to think about the relationship between the current concept ({current_concept}) and the next concept ({next_concept}), and generate the prompting question that logically transitions from the explanation towards exploring this next concept ({next_concept}).",
                        "- Use the conversation history and your explanation to choose the most helpful next question that deepens understanding of the phenomenon's scientific knowledge.",
                    )
                    state_prompt = state_prompt.replace(
                        "- The prompting question should NOT reveal '{next_concept}' directly or explicitly.",
                        "- Based on the conversation and scientific knowledge, ask a natural next question without relying on a specific next concept.",
                    )
                print(
                    f"[Concept Logic] Next concept: {next_concept_for_prompting}, Matched concepts: {matched_concepts}"
                )
            print("=" * 50)

        # Ensure state_prompt is not None before calling format_prompt
        if not state_prompt:
            print(
                f"WARNING: state_prompt is None before format_prompt (non-stream), current_state: {current_state}"
            )
            state_prompt = state_prompt_classification(
                current_state, child_question_level
            )
            if not state_prompt:
                state_prompt = "Respond to the child's question."

        if current_state == "scienceqa" and child_question_level is not None:
            state_prompt = format_prompt(
                state_prompt,
                phenomenon,
                messages,
                child_question_level,
                first_time_matched_concepts,
                app_version=app_version,
            )
        else:
            state_prompt = format_prompt(
                state_prompt, phenomenon, messages, app_version=app_version
            )

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
            matched_concepts_history.pop(conversation_id, None)
            scienceqa_turn_count.pop(conversation_id, None)
            all_concepts_matched_flag.pop(conversation_id, None)

        system_message = {"role": "system", "content": CURIO_SYSTEM_PROMPT}

        all_messages = (
            [system_message] + messages + [{"role": "user", "content": state_prompt}]
        )

        # Debug: print final prompt before response generation
        # try:
        #     print("\n=== AI Prompt (Non-Stream) ===")
        #     print(f"current_state: {current_state}")
        #     print(f"child_question_level: {child_question_level}")
        #     print(f"messages_count: {len(all_messages)}")
        #     print("--- system ---")
        #     print(system_message.get("content") or "")
        #     print("--- last_user_prompt (state_prompt) ---")
        #     print(state_prompt or "")
        #     print("=== End AI Prompt ===\n")
        # except Exception as e:
        #     print(f"Prompt print error (non-stream): {e}")

        response = client.chat.completions.create(
            model=OPENAI_CHAT_MODEL,
            messages=all_messages,
            max_tokens=OPENAI_MAX_TOKENS,
            temperature=1.0,
        )

        content = response.choices[0].message.content or ""

        # Print next concept used for this response (if in scienceqa state)
        if current_state == "scienceqa":
            print(
                f"[Response Generated] Next concept used for prompting question: {next_concept_for_prompting if next_concept_for_prompting else 'None (all concepts used)'}"
            )

        # Fix bold formatting for scienceqa-style responses
        if current_state == "scienceqa":
            original_content = content
            content = fix_scienceqa_bold_formatting(content)
            if content != original_content:
                print(f"Fixed bold formatting in {current_state} response")
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
            next_concept=next_concept_for_prompting
            if next_concept_for_prompting
            else None,
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

        return jsonify(
            {
                "response": content,
                "next_state": current_state,
                "first_time_matched_concepts": first_time_matched_concepts,
            }
        )

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
        curio_app_version = data.get("curio_app_version")
        try:
            app_version = (
                int(curio_app_version) if curio_app_version is not None else None
            )
        except (TypeError, ValueError):
            app_version = None

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

        # Reconstruct conversation history from database for existing conversations
        if conversation.created_at:
            (
                loaded_state_history,
                loaded_scienceqa_history,
                loaded_matched_concepts,
            ) = get_conversation_history_for_chat(conversation_id, db, phenomenon)
            state_history[conversation_id] = loaded_state_history
            scienceqa_history[conversation_id] = loaded_scienceqa_history
            matched_concepts_history[conversation_id] = loaded_matched_concepts

            # Reflection stage removed: count all scienceqa turns
            scienceqa_turn_count[conversation_id] = loaded_state_history.count(
                "scienceqa"
            )

            knowledge_base = json.load(open("knowledge/kg.json", "r"))
            phenomenon_map = {
                "balloon": "Hair Stands Up Near a Balloon",
                "bend": "Bending Water Stream with a Comb",
                "pepper": "Pepper Leaping up to Spoon",
            }
            phenomenon_key = phenomenon_map.get(
                phenomenon, "Hair Stands Up Near a Balloon"
            )
            concepts_dict = knowledge_base.get(phenomenon_key, {}).get("concepts", {})
            concept_names = list(concepts_dict.keys())
            all_concepts_matched_flag[conversation_id] = (
                len(loaded_matched_concepts) >= len(concept_names)
                if concept_names
                else False
            )

            print(
                f"[History Reconstruction] Loaded state: {loaded_state_history}, "
                f"scienceqa: {loaded_scienceqa_history}, "
                f"matched concepts: {loaded_matched_concepts}, "
                f"turn_count: {scienceqa_turn_count[conversation_id]}, "
                f"all_matched: {all_concepts_matched_flag[conversation_id]}"
            )

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
                    matched_knowledge_components=None,
                    next_concept=None,
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

            # If transitioning to scienceqa, reset turn count and classify question level
            if current_state == "scienceqa":
                # Reset turn count when entering scienceqa from another state
                if conv_state_history and conv_state_history[-1] != "scienceqa":
                    scienceqa_turn_count[conversation_id] = 0
                # Classify the child's question level (always use the scienceqa evaluator prompt)
                child_question_level = state_classification(
                    "scienceqa", messages, phenomenon
                )
                conv_scienceqa_history.append(child_question_level)
                print("\n=== Turn Evaluation (Stream) ===")
                print(f"Child's Question: {latest_user_message}")
                print(f"Evaluation Result: {child_question_level}")
                print("=" * 50)
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
            # In scienceqa state (stream): always stay in scienceqa until all concepts are matched
            scienceqa_turn_count[conversation_id] += 1
            turn_count = scienceqa_turn_count[conversation_id]

            # Stay in scienceqa state, classify the child's question level
            child_question_level = state_classification(
                "scienceqa", messages, phenomenon
            )
            conv_scienceqa_history.append(child_question_level)
            current_state = "scienceqa"
            state_prompt = state_prompt_classification(
                current_state, child_question_level
            )
            if latest_user_message:
                print("\n=== Turn Evaluation (Stream) ===")
                print(f"Child's Question: {latest_user_message}")
                print(f"Evaluation Result: {child_question_level} (turn {turn_count})")
                print("=" * 50)
            if not conv_state_history or conv_state_history[-1] != current_state:
                conv_state_history.append(current_state)
            eval_state = current_state

        # ============================================================
        # Response Generation (生成阶段)
        # ============================================================
        # A. Knowledge Retrieval (检索阶段) - for EXPLANATION only
        matched_kg = None  # For explanation
        next_concept_for_prompting = (
            None  # For prompting question (initialized for all states)
        )
        matched_concept = None  # Matched concept from knowledge retrieval
        first_time_matched_concepts = []  # For concept bubbles (stream path)

        if current_state == "scienceqa":
            # Load knowledge base to get concept list
            knowledge_base = open("knowledge/kg.json", "r").read()
            knowledge_base = json.loads(knowledge_base)
            phenomenon_map = {
                "balloon": "Hair Stands Up Near a Balloon",
                "bend": "Bending Water Stream with a Comb",
                "pepper": "Pepper Leaping up to Spoon",
            }
            phenomenon_key = phenomenon_map.get(
                phenomenon, "Hair Stands Up Near a Balloon"
            )
            concepts_dict = knowledge_base.get(phenomenon_key, {}).get("concepts", {})
            concept_names = list(concepts_dict.keys())

            # Get matched concepts history for this conversation
            matched_concepts = matched_concepts_history[conversation.id]

            # A. Knowledge Retrieval: Match concept for EXPLANATION (only for specific question levels)
            if child_question_level in [
                "factual",
                "explanatory",
                "general_causal",
                "specific_causal",
            ]:
                kg = knowledge_retrieval(messages, phenomenon, conversation.id, db)
                matched_kg = kg if kg else None  # Store for database and explanation
                print(
                    f"[Knowledge Retrieval] Matched component for explanation: {matched_kg if matched_kg else 'None'}"
                )

                # Parse matched concept and add to history if not already present
                if matched_kg and matched_kg != "":
                    try:
                        kg_list = (
                            json.loads(matched_kg)
                            if isinstance(matched_kg, str)
                            and matched_kg.startswith("[")
                            else json.loads(f'["{matched_kg}"]')
                            if isinstance(matched_kg, str)
                            else matched_kg
                        )
                        if isinstance(kg_list, list) and len(kg_list) > 0:
                            matched_concept_raw = kg_list[0]
                            # Normalize the concept name
                            for cn in concept_names:
                                if cn.lower() == matched_concept_raw.lower():
                                    matched_concept = cn
                                    # Add to matched concepts history if not already present
                                    if matched_concept not in matched_concepts:
                                        matched_concepts.append(matched_concept)
                                        first_time_matched_concepts.append(
                                            matched_concept
                                        )
                                        print(
                                            f"[Concept Logic] Added to matched history: {matched_concept}"
                                        )
                                    break
                    except (json.JSONDecodeError, TypeError, AttributeError):
                        pass

                # Find next concept: lowest order concept that hasn't been matched
                next_concept_for_prompting = None
                for concept_name in concept_names:
                    if concept_name not in matched_concepts:
                        next_concept_for_prompting = concept_name
                        break

                # If all concepts have been matched, set flag and transition to close
                if next_concept_for_prompting is None:
                    print(
                        "[Concept Logic] All concepts matched! Staying in scienceqa with empty next_concept."
                    )
                    all_concepts_matched_flag[conversation_id] = True

                # Extract definition and explanation for embedding in prompt
                definition = ""
                explanation = ""
                explanation_method = ""

                if matched_kg and matched_kg != "":
                    definition, explanation = extract_kg_definition_and_explanation(
                        matched_kg, phenomenon
                    )
                    if definition and explanation:
                        explanation_method = f"Here are the matched knowledge component's definition: {definition} and explanation: {explanation}. Based on the conversation history, use the provided knowledge component to explain the knowledge. The definition describes the formal definition of the concept, and the explanation describes how the concept works in the image. These two parts are for your reference. The explanation part of your response should be: (1) focus on the provided knowledge component and avoid introducing other concepts to confuse the child (e.g., if you are introducing 'electrons', do not mention 'charge'), (2) naturally flowing from the conversation history, and (3) must be within 30 words."
                    else:
                        explanation_method = (
                            "No strongly matched knowledge component is available for this turn. "
                            "Use the child's latest message and conversation history to respond naturally "
                            "and guide exploration, without directly revealing the phenomenon or introducing "
                            "any specific matched concept."
                        )
                else:
                    explanation_method = (
                        "No strongly matched knowledge component is available for this turn. "
                        "Use the child's latest message and conversation history to respond naturally "
                        "and guide exploration, without directly revealing the phenomenon or introducing "
                        "any specific matched concept."
                    )

                # Replace placeholders in prompt (only if still in scienceqa state)
                if current_state == "scienceqa":
                    state_prompt = state_prompt.replace(
                        "{explanation_method}", explanation_method
                    )
            else:
                # For irrelevant/no_question, use fallback explanation method
                explanation_method = (
                    "No strongly matched knowledge component is available for this turn. "
                    "Use the child's latest message and conversation history to respond naturally "
                    "and guide exploration, without directly revealing the phenomenon or introducing "
                    "any specific matched concept."
                )
                state_prompt = state_prompt.replace(
                    "{explanation_method}", explanation_method
                )
                matched_kg = None  # No knowledge retrieval for irrelevant/no_question
                # Find next concept: lowest order concept that hasn't been matched
                next_concept_for_prompting = None
                for concept_name in concept_names:
                    if concept_name not in matched_concepts:
                        next_concept_for_prompting = concept_name
                        break

                # If all concepts have been matched, transition to close
                if next_concept_for_prompting is None:
                    print(
                        "[Concept Logic] All concepts matched! Staying in scienceqa with empty next_concept."
                    )
                    all_concepts_matched_flag[conversation_id] = True

            # Replace placeholders for all scienceqa questions
            if current_state == "scienceqa":
                # Fill in current_concept from the matched knowledge component
                if not matched_concept:
                    # If matched_concept is empty, adjust the prompt wording to avoid
                    # "current concept ()" - use "the explanation part" instead.
                    state_prompt = state_prompt.replace(
                        "the current concept ({current_concept})",
                        "the explanation part",
                    )
                    state_prompt = state_prompt.replace("{current_concept}", "")
                else:
                    state_prompt = state_prompt.replace(
                        "{current_concept}", matched_concept
                    )

                state_prompt = state_prompt.replace(
                    "{next_concept}",
                    next_concept_for_prompting if next_concept_for_prompting else "",
                )
                # Only when next_concept is empty, relax the prompting-question constraints.
                if not next_concept_for_prompting:
                    state_prompt = state_prompt.replace(
                        "- You need to think about the relationship between the current concept ({current_concept}) and the next concept ({next_concept}), and generate the prompting question that logically transitions from the explanation towards exploring this next concept ({next_concept}).",
                        "- Use the conversation history and your explanation to choose the most helpful next question that deepens understanding of the phenomenon's scientific knowledge.",
                    )
                    state_prompt = state_prompt.replace(
                        "- The prompting question should NOT reveal '{next_concept}' directly or explicitly.",
                        "- Based on the conversation and scientific knowledge, ask a natural next question without relying on a specific next concept.",
                    )
                print(
                    f"[Concept Logic] Next concept: {next_concept_for_prompting}, Matched concepts: {matched_concepts}"
                )
            print("=" * 50)

        if not state_prompt:
            if current_state == "scienceqa" and not child_question_level:
                # Always use the scienceqa evaluator prompt for child-question level classification
                child_question_level = state_classification(
                    "scienceqa", messages, phenomenon
                )
            state_prompt = state_prompt_classification(
                current_state, child_question_level
            )
            if not state_prompt:
                state_prompt = "Respond to the child's question."

        if current_state == "scienceqa" and child_question_level is not None:
            state_prompt = format_prompt(
                state_prompt,
                phenomenon,
                messages,
                child_question_level,
                first_time_matched_concepts,
                app_version=app_version,
            )
        else:
            state_prompt = format_prompt(
                state_prompt, phenomenon, messages, app_version=app_version
            )

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
            matched_concepts_history.pop(conversation_id, None)
            scienceqa_turn_count.pop(conversation_id, None)
            all_concepts_matched_flag.pop(conversation_id, None)

        system_message = {"role": "system", "content": CURIO_SYSTEM_PROMPT}
        all_messages = (
            [system_message] + messages + [{"role": "user", "content": state_prompt}]
        )

        # Debug: print final prompt before response generation (stream)
        # try:
        #     print("\n=== AI Prompt (Stream) ===")
        #     print(f"current_state: {current_state}")
        #     print(f"child_question_level: {child_question_level}")
        #     print(f"messages_count: {len(all_messages)}")
        #     print("--- system ---")
        #     print((system_message.get("content") or ""))
        #     print("--- last_user_prompt (state_prompt) ---")
        #     print((state_prompt or ""))
        #     print("=== End AI Prompt ===\n")
        # except Exception as e:
        #     print(f"Prompt print error (stream): {e}")

        # Capture variables for use inside generate() function
        saved_child_question_level = child_question_level
        saved_matched_kg = matched_kg
        saved_next_concept_for_prompting = next_concept_for_prompting
        saved_first_time_matched = first_time_matched_concepts

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

                # Print next concept used for this response (if in scienceqa state)
                if current_state == "scienceqa":
                    print(
                        f"[Response Generated] Next concept used for prompting question: {saved_next_concept_for_prompting if saved_next_concept_for_prompting else 'None (all concepts used)'}"
                    )

                # Fix bold formatting for scienceqa responses
                if current_state == "scienceqa":
                    full_content = fix_scienceqa_bold_formatting(full_content)

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
                    next_concept=saved_next_concept_for_prompting
                    if saved_next_concept_for_prompting
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

                # Send final message (include first_time_matched_concepts for concept bubbles)
                yield f"data: {json.dumps({'type': 'done', 'response': full_content, 'next_state': current_state, 'first_time_matched_concepts': saved_first_time_matched})}\n\n"
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


def get_conversation_history_for_chat(conversation_id, db_session, phenomenon):
    """
    Reconstruct conversation history from database for use in chat_completion.
    Returns (state_history_list, scienceqa_history_list, matched_concepts_list).
    """
    state_history_list = []
    scienceqa_history_list = []
    matched_concepts_list = []

    knowledge_base = open("knowledge/kg.json", "r").read()
    knowledge_base = json.loads(knowledge_base)
    phenomenon_map = {
        "balloon": "Hair Stands Up Near a Balloon",
        "bend": "Bending Water Stream with a Comb",
        "pepper": "Pepper Leaping up to Spoon",
    }
    phenomenon_key = phenomenon_map.get(phenomenon, "Hair Stands Up Near a Balloon")
    concepts_dict = knowledge_base.get(phenomenon_key, {}).get("concepts", {})
    concept_names = list(concepts_dict.keys())

    messages = (
        db_session.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )

    for msg in messages:
        if msg.role == "assistant" and msg.state:
            if not state_history_list or state_history_list[-1] != msg.state:
                state_history_list.append(msg.state)

        if msg.evaluation_result and msg.evaluation_result in [
            "no_question",
            "irrelevant",
            "factual",
            "explanatory",
            "general_causal",
            "specific_causal",
        ]:
            scienceqa_history_list.append(msg.evaluation_result)

        if (
            msg.role == "assistant"
            and msg.state == "scienceqa"
            and msg.matched_knowledge_components
        ):
            try:
                matched_kg = msg.matched_knowledge_components
                kg_list = (
                    json.loads(matched_kg)
                    if isinstance(matched_kg, str) and matched_kg.startswith("[")
                    else json.loads(f'["{matched_kg}"]')
                    if isinstance(matched_kg, str)
                    else matched_kg
                )
                if isinstance(kg_list, list) and len(kg_list) > 0:
                    matched_concept_raw = kg_list[0]
                    for cn in concept_names:
                        if cn.lower() == matched_concept_raw.lower():
                            if cn not in matched_concepts_list:
                                matched_concepts_list.append(cn)
                            break
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass

    return state_history_list, scienceqa_history_list, matched_concepts_list


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

        loaded_state_history, loaded_scienceqa_history, loaded_matched_concepts = (
            get_conversation_history_for_chat(
                conversation_id, db, conversation.phenomenon
            )
        )

        state_history[conversation_id] = loaded_state_history
        scienceqa_history[conversation_id] = loaded_scienceqa_history
        matched_concepts_history[conversation_id] = loaded_matched_concepts

        scienceqa_turn_count[conversation_id] = loaded_state_history.count("scienceqa")

        knowledge_base = open("knowledge/kg.json", "r").read()
        knowledge_base = json.loads(knowledge_base)
        phenomenon_map = {
            "balloon": "Hair Stands Up Near a Balloon",
            "bend": "Bending Water Stream with a Comb",
            "pepper": "Pepper Leaping up to Spoon",
        }
        phenomenon_key = phenomenon_map.get(
            conversation.phenomenon, "Hair Stands Up Near a Balloon"
        )
        concepts_dict = knowledge_base.get(phenomenon_key, {}).get("concepts", {})
        concept_names = list(concepts_dict.keys())

        all_concepts_matched_flag[conversation_id] = (
            len(loaded_matched_concepts) >= len(concept_names)
            if concept_names
            else False
        )

        return jsonify(
            {
                "conversation_id": conversation_id,
                "session_id": conversation.session_id,
                "image_path": conversation.image_path,
                "phenomenon": conversation.phenomenon,
                "messages": result,
                "state_history": loaded_state_history,
                "scienceqa_history": loaded_scienceqa_history,
                "matched_concepts": loaded_matched_concepts,
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

        # Validate request content type
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 400

        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON in request body"}), 400

        text = data.get("text", "")
        if not text or not isinstance(text, str):
            return jsonify({"error": "No text provided or text is not a string"}), 400

        # Trim and validate text is not empty after trimming
        text = text.strip()
        if not text:
            return jsonify({"error": "Text is empty after trimming"}), 400

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
