
import os
from pathlib import Path
from groq import Groq
from dotenv import load_dotenv

# Load API key from .env
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)


def generate_story(code, language="English"):

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError("Groq API key not found. Check your .env file.")

    client = Groq(api_key=api_key)

    # Accept only English or Tamil
    language = language.strip().capitalize()

    if language not in ["English", "Tamil"]:
        language = "English"

    if language == "English":
        language_instruction = """
Write the entire response in simple, beginner-friendly English.
Do not include Tamil translations or Tamil sentences.
Keep Python keywords, variable names and code unchanged.
"""

        explanation_header = "Explanation"
        scene_header = "Description"
        concept_header = "Explanation"

    else:
        language_instruction = """
Write the entire response in natural, simple Tamil.
Do not include English translations or English sentences.
Keep Python keywords, variable names and code unchanged.
Use clear and grammatically correct Tamil.
"""

        explanation_header = "விளக்கம்"
        scene_header = "விளக்கம்"
        concept_header = "விளக்கம்"

    prompt = f"""
You are CodeStory AI, an expert Python programming teacher.

Your task is to understand the submitted Python code and explain
it in a beginner-friendly way.

LANGUAGE INSTRUCTION:
{language_instruction}

IMPORTANT RULES:

1. Explain ONLY the submitted Python code.
2. Understand the actual logic before writing the explanation.
3. Never invent variables, functions, operations or outputs.
4. Do not execute the submitted code.
5. Explain concepts as if teaching a beginner.
6. Follow the exact order of the program.
7. Do not skip important code statements or conditions.
8. If the code is incomplete or invalid, clearly mention it.
9. Do not assume user inputs that are not provided.
10. Keep explanations technically correct.
11. Use ONLY the selected language throughout the response.
12. Never provide bilingual explanations.
13. Do not translate Python keywords or variable names.

OUTPUT FORMAT:

# Story and Explanation

## 1. CODE UNDERSTANDING
Explain the overall purpose of the submitted program.
Mention its important operations and final result.

## 2. SIMPLE EXPLANATION
Explain the code step by step in the original execution order.

Use this table:

| Step | Code | {explanation_header} |

Include all important statements.
Combine closely related statements only when appropriate.

## 3. STORY TITLE
Create a short, interesting title based on the actual program.

## 4. STORY
Convert the actual program logic into a simple real-world story.

Rules:
- The story must match the submitted code.
- Explain what happens and in what order.
- Do not add features that the code does not contain.
- Use an easy-to-understand example.

## 5. STORY SCENES
Divide the program into 3 to 6 meaningful scenes.

Use this table:

| Scene | {scene_header} |

Each scene must represent an actual operation in the program.

## 6. LEARNING POINTS
Identify the actual Python concepts used in the submitted code.

Use this table:

| Concept | {concept_header} |

Explain concepts such as variables, input(), print(), operators,
conditions, loops and functions only when they are actually present.

## 7. SUMMARY
Give a short and accurate summary in the selected language.

FORMATTING RULES:

- Use proper Markdown headings.
- Use bold formatting for important terms.
- Use readable Markdown tables.
- Format Python statements using backticks.
- Do not output escaped Markdown symbols such as \\*\\*.
- Avoid unnecessary repetition.
- Do not add unrelated sections.
- Do not include both English and Tamil in the same response.

Submitted Python Code:

{code}
"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are CodeStory AI, a friendly and accurate "
                    "Python teacher. Follow the requested seven-section "
                    "structure and use only the selected language."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.3,
        max_completion_tokens=4000
    )

    result = response.choices[0].message.content

    if not result:
        raise ValueError("The AI returned an empty response. Please try again.")

    return result
