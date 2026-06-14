from core.logger import logger
from core.models import ask, MODELS

def run_debate(prompt, history=None, rounds=2):
    """
    2-round debate:
    Round 1: Research → Critique → Rewrite
    Round 2: Critique again → Final Rewrite
    Then vote
    """
    logger.info(f"DEBATE: Starting {rounds}-round debate")

    # ── ROUND 1: RESEARCH ──
    logger.info("DEBATE: Round 1 - Research")
    answers = {}
    answers["LLAMA3"]  = ask(MODELS["general"],  prompt, history, "general",  "research")
    answers["MISTRAL"] = ask(MODELS["reason"],   prompt, history, "reason",   "research")
    answers["QWEN"]    = ask(MODELS["analysis"], prompt, history, "analysis", "research")

    all_rounds = {"round1_research": dict(answers)}

    for round_num in range(1, rounds + 1):
        logger.info(f"DEBATE: Round {round_num} - Critique")
        critiques = {}
        for my_name, my_key in [("LLAMA3","general"),("MISTRAL","reason"),("QWEN","analysis")]:
            others = "\n\n".join(f"[{n}]:\n{a}" for n,a in answers.items() if n != my_name)
            cp = (
                f"Question: {prompt}\n\n"
                f"Your current answer:\n{answers[my_name]}\n\n"
                f"Other models' answers:\n{others}\n\n"
                f"This is round {round_num} of {rounds}. "
                "Point out specific factual mistakes, missing info, or weak reasoning "
                "in the OTHER models' answers. Use bullet points. Be precise."
            )
            critiques[my_name] = ask(MODELS[my_key], cp, None, my_key, "critique")

        logger.info(f"DEBATE: Round {round_num} - Rewrite")
        new_answers = {}
        for my_name, my_key in [("LLAMA3","general"),("MISTRAL","reason"),("QWEN","analysis")]:
            received = "\n\n".join(
                f"[{n} criticized you]:\n{c}" for n,c in critiques.items() if n != my_name
            )
            rp = (
                f"Question: {prompt}\n\n"
                f"Your previous answer:\n{answers[my_name]}\n\n"
                f"Criticism received:\n{received}\n\n"
                f"Round {round_num} of {rounds}. "
                "Rewrite your answer incorporating valid corrections. "
                "Make it the most accurate and complete answer possible."
            )
            new_answers[my_name] = ask(MODELS[my_key], rp, None, my_key, "rewrite")

        all_rounds[f"round{round_num}_critiques"] = critiques
        all_rounds[f"round{round_num}_rewrites"] = dict(new_answers)
        answers = new_answers  # use latest answers for next round

    return all_rounds, answers  # all_rounds for history, answers = final rewrites