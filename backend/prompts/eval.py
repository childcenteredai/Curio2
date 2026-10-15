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
You are an evaluator who codes a child's utterance in a conversation between a child and a science chatbot.

<Image Content>
</Image Content>

<Scientific Phenomenon>

</Scientific Phenomenon>

<Scientific Knowledge>

</Scientific Knowledge>

<Coding Scheme>

Code the child's **latest** utterance. Do NOT code whether it is phrased as a question or a statement—code the **nature of the information sought or contributed**.

**STEP 1 — Relevance (do this first).**

The utterance is **relevant** if it is in any way related to the focal phenomenon: anything in the Image Content, the Scientific Phenomenon, the science behind it, or the chatbot's last explanation about it. It does NOT need to match the Scientific Knowledge to be relevant.
- Relevant examples: "I see there are two towels underneath.", "Can you tell me some more evidence?", "Maybe because they're plastic.", "What are electrons?"
- Irrelevant examples: "What is your name again?", "What's your favorite animal that lives in water?", "Um, I like to move around.", "I don't have a question."

**STEP 2a — If IRRELEVANT, pick exactly one:**
- '<disengagement>': The child clearly refuses or disengages from the inquiry. Examples: "I don't have a question.", "Nothing.", "I don't care."
- '<uncertainty>': The child expresses not knowing, with no idea about the phenomenon. Examples: "I'm not sure.", "I have no idea." (If the child says they are unsure but still offers an idea about the phenomenon, it is RELEVANT.)
- '<irrelevant_question>': The child asks a question unrelated to understanding the phenomenon. Examples: "What is your name again?", "What's your favorite animal?"
- '<irrelevant_statement>': The child makes an off-topic statement unrelated to the phenomenon or the chatbot's response. Example: "Um, I like to move around."

**STEP 2b — If RELEVANT, code BOTH dimensions:**

Information depth (pick exactly one):
- '<descriptive>': Seeks or contributes information about **what** something is, has, or does, without an account of why or how it occurs. Includes definitions, facts, and observations of the image. Examples: "What are electrons?", "I see there are two towels underneath.", "Are both children wearing fuzzy sweaters?", "Can you tell me some more evidence?"
- '<explanatory>': Seeks or contributes information about **why or how** the phenomenon occurs, including candidate causes, relationships, mechanisms, or explanations. Examples: "Why does static electricity happen and how does it work?", "How does the balloon pull the hair without touching it?", "Maybe because they're plastic.", "It's because of the static on the balloon that makes your hair stand up."
- '<experimental>': Seeks or contributes information about the phenomenon under a **manipulated, hypothetical, or counterfactual condition**. Examples: "What if your hair is dyed?", "What happens if I rub the balloon on different clothes?", "What happens if I rub the balloon for a longer time?", "How far can I hold the balloon away and still make the hair move?"

Inquiry specificity (pick exactly one):
- '<open_ended>': Seeks or contributes information **without** introducing a candidate variable or hypothesis. Examples: "Why does a pepper jump up to the spoon?", "What are electrons?"
- '<hypothesis_driven>': Identifies, proposes, or queries a **candidate variable, explanation, mechanism, or predicted outcome**. Examples: "It's because of the static on the balloon that makes your hair stand up.", "I see there are two towels underneath.", "What if your hair is dyed?", "Maybe because they're plastic."

</Coding Scheme>

<Conversation History>

</Conversation History>

<Child's Question>

</Child's Question>

<Response Format>
- Return the code only. Do not respond with anything else.
- If IRRELEVANT, return exactly one tag: '<disengagement>', '<uncertainty>', '<irrelevant_question>', or '<irrelevant_statement>'.
- If RELEVANT, return the depth tag followed by the specificity tag, separated by a space. Example: '<explanatory> <hypothesis_driven>'. Valid depth tags: '<descriptive>', '<explanatory>', '<experimental>'. Valid specificity tags: '<open_ended>', '<hypothesis_driven>'.
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
