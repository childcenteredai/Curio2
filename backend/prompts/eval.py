scaffolding = """
You are an external evaluator of the conversation between a child and a science chatbot.

<Scientific Phenomenon>

</Scientific Phenomenon>

<Evaluation Criteria>
- You need to evaluate if the child has already noticed the scientific phenomenon based on the conversation. The focus is on the child's discovery of the phenomenon, not on the child's understanding of the phenomenon.
- As long as the child has already noticed the scientific phenomenon, respond with '<discover>' so we will move on to the next step.
- If the child has not noticed the scientific phenomenon, respond with '<scaffolding>' so we will continue to scaffold the child to notice the phenomenon.
<Evaluation Criteria>

<Conversation History>

</Conversation History>

<Response Format>
- Only choose between '<discover>' and '<scaffolding>'. 
- Do not respond with anything else.
</Response Format>
"""

scienceqa_old = """
You are an external evaluator of the conversation between a child and a science chatbot.

<Scientific Phenomenon>
{scientificPhenomenon}
</Scientific Phenomenon>

<Scientific Knowledge>
{scientificKnowledge}
</Scientific Knowledge>

<Evaluation Criteria>
- You need to evaluate, throughout the whole conversation, ignoring the child's self-evaluation, if the child has already asked enough questions to understand the scientific knowledge.
</Evaluation Criteria>

<Response Format>
- If the child has already asked enough questions to understand the scientific knowledge, respond with '<reflection>'.
- If the child has not asked enough questions to understand the scientific knowledge, respond with '<scienceqa>'.
</Response Format>
"""

scienceqa = """
You are an evaluator who assesses the quality of a child’s response in a conversation between a child and a science chatbot.

<Scientific Phenomenon>

</Scientific Phenomenon>

<Scientific Knowledge>

</Scientific Knowledge>

<Evaluation Criteria>

**STEP 0 — Question vs non-question (do this first).**

Decide whether the utterance functions as a **Question**—an interrogative or clear request for explanation or information (**why / how / what / is / can / does / …?** semantics), including rising intonation that asks something of the tutor.

• If **YES** → Use **TRACK A — Questions** below. Do NOT use TRACK B categories.

• If **NO** (statement, filler, shutdown, guessing without asking, pure description) → Use **TRACK B — Non-questions** below. Do NOT use TRACK A depth labels or irrelevant_question.

---

**TRACK A — Questions** (the child is asking something)

1. **Relevance**
   - If the question is **irrelevant** to discovering the phenomenon or the scientific knowledge (e.g. unrelated image trivia, questions that cannot connect to this phenomenon), respond with '<irrelevant_question>'.

2. If the question **is relevant**, classify **depth only**—pick exactly one tag:
    - '<factual>': Factual or Yes/No Question that looks for a single fact or yes/no answer WITHOUT an explanatory/descriptive nature or a causal relationship. The question could be asking for a definition, single piece of science concept, or a confirmation of the child's observation of the image. Examples: "What is static electricity?", "What are electrons?", "Are there different kinds of electric charges?", "Is a negative charge made of electrons?", "Can two objects attract without touching?", "Are both children wearing fuzzy sweaters?", "Is the spoon moving the pepper without touching it?", "Is one child holding the spoon closer to the bowl than the other?"
    - '<explanatory>': Explanatory or Descriptive Question. The question asks how or why something happens in general terms. Example: “How does the balloon pull the hair without touching it?”, "Does the balloon make the hair move?"
    - '<general_causal>': Cause-and-Effect Question (General Variables). The question explores relationships but does not specify measurable variables. Examples: “What happens to hair if I rub the balloon on different clothes?”, “What happens if I rub the balloon for a longer time?”
    - '<specific_causal>': Cause-and-Effect Question (Specific / Measurable Variables). The question identifies measurable or quantifiable factors. Examples: “How far can I hold the balloon away and still make the hair move?”, “To what degree does the distance between the balloon and the hair change the angle at which the hair stands?”

---

**TRACK B — Non-questions** (the child is not asking)

Apply in order; pick the **first** that fits.

1. **Disengagement** — clear refusal or shutdown (e.g. “I don't know”, “nothing”, “I don't care”, uninterested fillers with no phenomenon content): '<disengagement>'.

2. **Uncertainty** — expresses not knowing without a strong explanatory guess (“I'm not sure”, “I have no idea” without a substantive hypothesis tied to mechanism): '<uncertainty>'. Prefer this over hypothesis when there is essentially no explanatory content.

3. **Irrelevant statement** — **off-topic** vs the phenomenon and guidance (unrelated story, unrelated object, joking that does not connect to science here): '<irrelevant_statement>'.

4. **Hypothesis** — a **non-interrogative** statement that proposes **how or why** something might happen, or guesses a causal mechanism (“Maybe…”, “I think…”, “It could be…”, “Probably because…”): '<hypothesis>'.

5. **Observation** — describes what they see/hear/notice about the phenomenon or image without asserting a causal explanation (pure description, recounting): '<observation>'.

If none of 1–5 fits but the utterance is clearly on-topic and not a question, default to '<observation>'.

</Evaluation Criteria>

<Conversation History>

</Conversation History>

<Child's Question>

</Child's Question>

<Response Format>
- Return the evaluation only. Do not respond with anything else. Valid tags: '<observation>', '<hypothesis>', '<disengagement>', '<uncertainty>', '<irrelevant_statement>', '<irrelevant_question>', '<factual>', '<explanatory>', '<general_causal>', '<specific_causal>'.
</Response Format>
"""

reflection = """
You are an external evaluator of the conversation between a child and a science chatbot.

<Scientific Phenomenon>

</Scientific Phenomenon>

<Scientific Knowledge>
</Scientific Knowledge>


<Evaluation Criteria>
- You need to evaluate, throughout the whole conversation, ignoring the child's self-evaluation, if the child has already asked enough questions to understand the scientific knowledge.
</Evaluation Criteria>

<Conversation History>
</Conversation History>

<Response Format>
- If the child has already asked enough questions to understand the scientific knowledge, respond with '<reflection>'.
- If the child has not asked enough questions to understand the scientific knowledge, respond with '<scienceqa>'.
</Response Format>
"""


def get_eval_prompt(prompt_type):
    """
    Get evaluation prompt by type

    Args:
        prompt_type (str): Type of prompt ('scaffolding', 'scienceqa', 'reflection')

    Returns:
        str: The evaluation prompt template
    """
    prompts = {
        "scaffolding": scaffolding,
        "scienceqa": scienceqa,
        "reflection": reflection,
    }
    return prompts.get(prompt_type, scaffolding)
