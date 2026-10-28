
import markdown
import bleach
import json
import os
import re

from groq import Groq

from flask import (
    Flask, render_template, request,
    send_file, redirect, url_for, session
)

from functools import wraps
from pathlib import Path
from io import BytesIO
from xml.sax.saxutils import escape

from story_generator import generate_story

from database import (
    create_tables,
    register_user,
    login_user,
    save_story,
    get_user_stories
)

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Preformatted
)


# -----------------------------------------
# FORMAT GENERATED STORY
# -----------------------------------------

def format_story(text):

    text = re.sub(
        r"\A\s*#{1,2}\s*(?:✨\s*)?Story and Explanation\s*\n+",
        "",
        text,
        count=1,
        flags=re.IGNORECASE
    )

    html = markdown.markdown(
        text,
        extensions=["tables", "fenced_code"]
    )

    allowed_tags = [
        "h1", "h2", "h3", "h4",
        "p", "strong", "em",
        "ul", "ol", "li",
        "table", "thead", "tbody",
        "tr", "th", "td",
        "pre", "code", "blockquote",
        "hr", "br"
    ]

    return bleach.clean(
        html,
        tags=allowed_tags,
        strip=True
    )


# -----------------------------------------
# FLASK CONFIGURATION
# -----------------------------------------

app = Flask(__name__)

app.jinja_env.filters["format_story"] = format_story

app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "codestory-local-development-key"
)

BASE_DIR = Path(__file__).resolve().parent

FONT_PATH = BASE_DIR / "fonts" / "Nirmala.ttc"

create_tables()


# -----------------------------------------
# LOGIN PROTECTION
# -----------------------------------------

def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if "user_id" not in session:
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return wrapper


# -----------------------------------------
# HOME PAGE
# -----------------------------------------

@app.route("/")
def home():

    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


# -----------------------------------------
# REGISTER
# -----------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            return render_template(
                "register.html",
                error="Please fill in all fields."
            )

        if len(password) < 8:
            return render_template(
                "register.html",
                error="Password must contain at least 8 characters."
            )

        if len(name) > 100 or len(email) > 254:
            return render_template(
                "register.html",
                error="Please enter valid details."
            )

        success = register_user(name, email, password)

        if success:
            return redirect(url_for("login"))

        return render_template(
            "register.html",
            error="This email is already registered."
        )

    return render_template("register.html")


# -----------------------------------------
# LOGIN
# -----------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = login_user(email, password)

        if user:

            session.clear()

            session["user_id"] = user["id"]
            session["user_name"] = user["name"]

            return redirect(url_for("dashboard"))

        return render_template(
            "login.html",
            error="Invalid email or password."
        )

    return render_template("login.html")


# -----------------------------------------
# DASHBOARD
# -----------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():

    user = {
        "name": session.get("user_name", "User")
    }

    stories = get_user_stories(session["user_id"])

    return render_template(
        "dashboard.html",
        user=user,
        stories=stories
    )


# -----------------------------------------
# LOGOUT
# -----------------------------------------

@app.route("/logout")
@login_required
def logout():

    session.clear()

    return redirect(url_for("login"))


# -----------------------------------------
# NEW STORY PAGE
# -----------------------------------------

@app.route("/new-story")
@login_required
def new_story():

    return render_template("index.html")


# -----------------------------------------
# GENERATE STORY
# -----------------------------------------

@app.route("/generate", methods=["POST"])
@login_required
def generate():

    code = request.form.get("code", "").strip()

    language = request.form.get(
        "language",
        "English"
    ).strip()

    if language not in ["English", "Tamil"]:
        language = "English"

    if not code:
        return render_template(
            "index.html",
            error="Please enter your Python code."
        )

    if len(code) > 12000:
        return render_template(
            "index.html",
            error="Code is too long. Please enter a shorter program."
        )

    # Check Python syntax without executing code
    try:
        compile(code, "<user_code>", "exec")

    except SyntaxError as e:
        return render_template(
            "index.html",
            error=f"Syntax Error: {e.msg} (Line {e.lineno})"
        )

    # Generate story using Groq
    try:

        story = generate_story(code, language)

        # Save story in the user's account
        save_story(
            session["user_id"],
            code,
            story,
            language
        )

        return render_template(
            "story.html",
            story=story,
            code=code,
            language=language
        )

    except Exception as e:

        print("Story Generation Error:", str(e))

        return render_template(
            "index.html",
            error="Unable to generate the story. Please try again."
        )


# -----------------------------------------
# GROQ CLIENT
# -----------------------------------------

def get_groq_client():

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError("Groq API key not found.")

    return Groq(api_key=api_key)


# -----------------------------------------
# FEATURE 1: PREDICT THE OUTPUT
# -----------------------------------------

@app.route("/predict-output", methods=["GET", "POST"])
@login_required
def predict_output():

    prediction = None
    code = ""
    error = None

    if request.method == "POST":

        code = request.form.get("code", "").strip()

        if not code:

            error = "Please enter your Python code."

        elif len(code) > 12000:

            error = "Code is too long. Please enter a shorter program."

        else:

            try:

                # Check syntax only. Never execute submitted code.
                compile(code, "<user_code>", "exec")

                client = get_groq_client()

                response = client.chat.completions.create(
                    model="openai/gpt-oss-120b",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a careful Python programming teacher. "
                                "Predict the output of the submitted code by "
                                "reasoning about it. Never claim that you executed "
                                "the code. If input() is used, explain that the "
                                "output depends on the user's input. Show the "
                                "expected output and a short step-by-step explanation. "
                                "Do not invent missing inputs or outputs."
                            )
                        },
                        {
                            "role": "user",
                            "content": (
                                "Predict the output of this Python program.\n\n"
                                "Python code:\n" + code
                            )
                        }
                    ],
                    temperature=0.2,
                    max_completion_tokens=1500
                )

                prediction = response.choices[0].message.content

            except SyntaxError as e:

                error = f"Syntax Error: {e.msg} (Line {e.lineno})"

            except Exception as e:

                print("Output Prediction Error:", str(e))

                error = "Unable to predict the output. Please try again."

    return render_template(
        "predict_output.html",
        code=code,
        prediction=prediction,
        error=error
    )


# -----------------------------------------
# FEATURE 2: GENERATE STORY-BASED QUIZ
# -----------------------------------------

@app.route("/story-quiz", methods=["POST"])
@login_required
def story_quiz():

    code = request.form.get("code", "").strip()

    story = request.form.get("story", "").strip()

    language = request.form.get(
        "language",
        "English"
    ).strip()

    if language not in ["English", "Tamil"]:
        language = "English"

    if not code or not story:
        return redirect(url_for("new_story"))

    try:

        client = get_groq_client()

        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a Python programming quiz creator. "
                        "Create exactly 5 multiple-choice questions based only "
                        "on the submitted Python code and its explanation. "
                        "Use the requested language only; do not mix English "
                        "and Tamil. Return valid JSON only with this structure: "
                        '{"questions": [{"question": "...", '
                        '"options": ["...", "...", "...", "..."], '
                        '"answer": 0, "explanation": "..."}]}. '
                        "The answer must be the zero-based index (0 to 3) of "
                        "the correct option. Include exactly 5 questions."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Language: {language}\n\n"
                        f"Python code:\n{code}\n\n"
                        f"Generated story:\n{story}"
                    )
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_completion_tokens=2500
        )

        result = json.loads(
            response.choices[0].message.content
        )

        questions = result.get("questions", [])

        if not isinstance(questions, list) or len(questions) != 5:
            raise ValueError(
                "The model did not return exactly 5 questions."
            )

        for question in questions:

            if not isinstance(question, dict):
                raise ValueError("Invalid question format.")

            options = question.get("options")

            answer = question.get("answer")

            if (
                not isinstance(question.get("question"), str)
                or not isinstance(options, list)
                or len(options) != 4
                or not all(
                    isinstance(option, str)
                    for option in options
                )
                or not isinstance(answer, int)
                or isinstance(answer, bool)
                or answer not in range(4)
            ):

                raise ValueError(
                    "Invalid quiz question or answer format."
                )

            question.setdefault("explanation", "")

        # Store quiz information in session
        session["current_quiz"] = questions
        session["quiz_story"] = story
        session["quiz_code"] = code
        session["quiz_language"] = language

        return render_template(
            "quiz.html",
            questions=questions,
            quiz=questions,
            story=story,
            code=code,
            language=language
        )

    except Exception as e:

        print("Quiz Generation Error:", str(e))

        return render_template(
            "quiz.html",
            questions=[],
            quiz=[],
            story=story,
            code=code,
            language=language,
            error="Unable to generate the quiz. Please try again."
        )


# -----------------------------------------
# CHECK STORY-BASED QUIZ ANSWERS
# -----------------------------------------

@app.route("/check-quiz", methods=["POST"])
@login_required
def check_quiz():

    questions = session.get("current_quiz", [])

    if not questions:
        return redirect(url_for("new_story"))

    score = 0

    results = []

    for i, question in enumerate(questions):

        selected = request.form.get(
            f"answer_{i}",
            ""
        )

        correct = question["answer"]

        is_correct = (
            selected.isdigit()
            and int(selected) == correct
        )

        if is_correct:
            score += 1

        results.append({
            "selected": (
                int(selected)
                if selected.isdigit()
                else -1
            ),
            "correct": correct,
            "is_correct": is_correct,
            "explanation": question.get(
                "explanation",
                ""
            )
        })

    return render_template(
        "quiz.html",
        questions=questions,
        quiz=questions,
        quiz_results=results,
        quiz_score=score,
        story=session.get("quiz_story", ""),
        code=session.get("quiz_code", ""),
        language=session.get("quiz_language", "English")
    )


# -----------------------------------------
# DOWNLOAD STORY AS PDF
# -----------------------------------------

@app.route("/download-pdf", methods=["POST"])
@login_required
def download_pdf():

    code = request.form.get("code", "")

    story = request.form.get("story", "")

    language = request.form.get(
        "language",
        "English"
    )

    if language not in ["English", "Tamil"]:
        language = "English"

    if not FONT_PATH.exists():

        return (
            "Nirmala.ttc was not found inside the fonts folder.",
            500
        )

    try:

        # Register Tamil-supported font
        pdfmetrics.registerFont(
            TTFont(
                "Nirmala",
                str(FONT_PATH),
                subfontIndex=0
            )
        )

        buffer = BytesIO()

        document = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=45,
            leftMargin=45,
            topMargin=45,
            bottomMargin=45
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "PDFTitle",
            parent=styles["Title"],
            fontName="Nirmala",
            fontSize=20,
            leading=26,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#5635a5"),
            spaceAfter=20
        )

        heading_style = ParagraphStyle(
            "SectionHeading",
            parent=styles["Heading2"],
            fontName="Nirmala",
            fontSize=14,
            leading=20,
            textColor=colors.HexColor("#6842c2"),
            spaceBefore=14,
            spaceAfter=8
        )

        body_style = ParagraphStyle(
            "StoryBody",
            parent=styles["BodyText"],
            fontName="Nirmala",
            fontSize=10,
            leading=16,
            spaceAfter=6,
            wordWrap="CJK"
        )

        code_style = ParagraphStyle(
            "CodeStyle",
            parent=styles["Code"],
            fontName="Nirmala",
            fontSize=8,
            leading=12,
            leftIndent=8,
            rightIndent=8,
            backColor=colors.HexColor("#f3f0fa"),
            borderPadding=8
        )

        content = []

        content.append(
            Paragraph(
                "CodeTales",
                title_style
            )
        )

        content.append(
            Paragraph(
                "Your Submitted Python Code",
                heading_style
            )
        )

        content.append(
            Preformatted(
                escape(code),
                code_style,
                maxLineLength=95
            )
        )

        content.append(Spacer(1, 18))

        content.append(
            Paragraph(
                "Story and Explanation",
                heading_style
            )
        )

        for line in story.splitlines():

            clean_line = line.strip()

            if not clean_line:

                content.append(
                    Spacer(1, 5)
                )

            elif clean_line.startswith("#"):

                heading_text = clean_line.lstrip("#").strip()

                content.append(
                    Paragraph(
                        escape(heading_text),
                        heading_style
                    )
                )

            else:

                content.append(
                    Paragraph(
                        escape(line),
                        body_style
                    )
                )

        document.build(content)

        buffer.seek(0)

        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"CodeTales_{language}.pdf",
            mimetype="application/pdf"
        )

    except Exception as e:

        print("PDF Generation Error:", str(e))

        return (
            "Unable to generate PDF. Please check the terminal for details.",
            500
        )


# -----------------------------------------
# RUN FLASK APPLICATION
# -----------------------------------------

if __name__ == "__main__":

    app.run(debug=True)
