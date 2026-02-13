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
1. Start by checking if the child's response is *not a question* (e.g., a pure observation, statement, description, or retelling), respond with '<no_question>'. Return <no_question> ONLY if the utterance does NOT function as inquiry. Note that hypotheses or guesses in the format of plain statement (e.g., “Maybe…”, “I think…”, “It could be…”) should be treated as inquiry moves IF they explore a possible explanation or mechanisms. If the child's response is truly not a question, you can ignore the rest of the evaluation criteria.
2. Next, check if the child’s response is a question but is *irrelevant to the given scientific knowledge topic*, for example, the child is asking about irrelevant image details, or, as long as the child's question cannot lead to the discovery of the scientific knowledge behind the phenomenon, respond with '<irrelevant>'. Example: "Is it magnetic?", "Is it sticky?", "Is it chemical?". If the child's question is irrelevant, you can ignore the rest of the evaluation criteria.
3. Finally, if the child’s response is a question and is **relevant** to the given scientific knowledge topic, for example, the child is inferring or exploring the scientific knowledge behind the phenomenon, evaluate it based on the depth and specificity of reasoning:
    - '<factual>': Factual or Yes/No Question that looks for a single fact or yes/no answer WITHOUT an explanatory/descriptive nature or a causal relationship. The question could be asking for a definition, single piece of science concept, or a confirmation of the child's observation of the image. Examples: "What is static electricity?", "What are electrons?", "Are there different kinds of electric charges?", "Is a negative charge made of electrons?", "Can two objects attract without touching?", "Are both children wearing fuzzy sweaters?", "Is the spoon moving the pepper without touching it?", "Is one child holding the spoon closer to the bowl than the other?"
    - '<explanatory>': Explanatory or Descriptive Question. The question asks how or why something happens in general terms. Example: “How does the balloon pull the hair without touching it?”, "Does the balloon make the hair move?"
    - '<general_causal>': Cause-and-Effect Question (General Variables). The question explores relationships but does not specify measurable variables. Examples: “What happens to hair if I rub the balloon on different clothes?”, “What happens if I rub the balloon for a longer time?”
    - '<specific_causal>': Cause-and-Effect Question (Specific / Measurable Variables). The question identifies measurable or quantifiable factors. Examples: “How far can I hold the balloon away and still make the hair move?”, “To what degree does the distance between the balloon and the hair change the angle at which the hair stands?”
</Evaluation Criteria>

<Conversation History>

</Conversation History>

<Child's Question>

</Child's Question>

<Response Format>
- Return the evaluation only. Do not respond with anything else. E.g., '<factual>', '<explanatory>', '<general_causal>', '<specific_causal>', '<no_question>', '<irrelevant>'.
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
