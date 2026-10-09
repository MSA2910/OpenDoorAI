from flask import Flask, render_template, request
from dotenv import load_dotenv
from openai import OpenAI
import os
import re
import markdown

# --------------------------------------------------
# Configuration
# --------------------------------------------------

load_dotenv()

api_key = os.getenv("OPENROUTER_API_KEY")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key
) if api_key else None

app = Flask(__name__)


# --------------------------------------------------
# Markdown filter for headings, lists, code and tables
# --------------------------------------------------

@app.template_filter("markdown_to_html")
def markdown_to_html_filter(text):
    return markdown.markdown(
        text or "",
        extensions=["fenced_code", "tables"]
    )


# --------------------------------------------------
# Shared learning-plan formatting instructions
# --------------------------------------------------

PLAN_FORMAT = """
Format the learning plan as a structured, beginner-friendly study guide.

Requirements:
1. Begin with a short overview of the subject.
2. Create 6–10 numbered topics in logical learning order.
3. Use this heading format for each topic:
   ## Topic 1: Introduction to Python
   ## Topic 2: Variables and Data Types
4. Under each topic, include a short description.
5. Add a heading called "What You'll Learn".
6. Include 3–5 concise bullet points for each topic.
7. Add a Markdown table for each topic using these columns:
   | Concept | Explanation | Learning Outcome |
8. Include 2–4 useful rows in each table.
9. Keep paragraphs short and explanations easy to understand.
10. Use examples relevant to the actual subject.
11. Follow the supplied university syllabus when available.
12. Do not invent official university requirements.
13. Do not generate full lessons yet. This is the learning plan only.
14. Do not place the entire response inside a code block.
15. End with a short summary.

The website already provides action buttons, so do not ask the student
to select an action inside the generated plan.
"""


# --------------------------------------------------
# Home page
# --------------------------------------------------

@app.route("/")
def home():
    return render_template("index.html")


# --------------------------------------------------
# Study page
# --------------------------------------------------

@app.route("/study")
def study():
    return render_template("study.html")


# --------------------------------------------------
# Learn page
# --------------------------------------------------

@app.route("/learn", methods=["POST"])
def learn():
    topic = request.form.get("topic", "").strip()

    return render_template("learn.html", topic=topic)


# --------------------------------------------------
# Lesson page
# Supports /lesson?topic=Python&number=2
# --------------------------------------------------

@app.route("/lesson")
def lesson():
    topic = request.args.get("topic", "Your Topic")
    number = request.args.get("number", 1, type=int)

    return render_template(
        "lesson.html",
        topic=topic,
        number=number
    )


# --------------------------------------------------
# Generate an AI learning plan
# --------------------------------------------------

@app.route("/start-study", methods=["POST"])
def start_study():
    subject = request.form.get("subject", "").strip()
    syllabus = request.form.get("syllabus", "").strip()

    if not subject and not syllabus:
        return "Please enter a subject or syllabus.", 400

    if not client:
        return (
            "OpenRouter API key is missing. "
            "Please check your .env file."
        ), 500

    if subject and syllabus:
        prompt = f"""
The student wants to study: {subject}

University syllabus supplied by the student:
{syllabus}

Create a learning plan based primarily on the supplied syllabus.
Preserve the syllabus topics and arrange them in a sensible learning order.

{PLAN_FORMAT}
"""

    elif subject:
        prompt = f"""
The student wants to study: {subject}

Create a suggested learning plan from beginner to advanced.
Choose appropriate topics for the subject.

{PLAN_FORMAT}
"""

    else:
        prompt = f"""
The student supplied this university syllabus:

{syllabus}

Infer the likely subject and create a learning plan based primarily
on the supplied syllabus. Keep the topics relevant to the syllabus.

{PLAN_FORMAT}
"""

    try:
        print("STEP 1: Reached OpenRouter request")

        response = client.chat.completions.create(
            model="openrouter/free",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are OpenDoor AI, a patient and accurate "
                        "Python and computer science study tutor. "
                        "Generate complete, useful learning plans in "
                        "valid Markdown. Never return an empty response."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=4000
        )

        print("STEP 2: OpenRouter returned a response")

        print("Finish reason:", response.choices[0].finish_reason)
        print("Response message:", response.choices[0].message)

        plan = response.choices[0].message.content

        if not plan or not plan.strip():
            app.logger.error(
                "OpenRouter returned no text. Response: %r",
                response
            )
            return (
                "The AI provider returned no text. Please try again. "
                "The selected free model may be temporarily unavailable.",
                502
            )

        print("\n===== AI GENERATED PLAN =====")
        print(repr(plan))
        print("===== END OF PLAN =====\n")

        return render_template(
            "tutor_plan.html",
            subject=subject or "Your Study Plan",
            plan=plan
        )

    except Exception:
        app.logger.exception("OpenRouter learning-plan request failed")

        return (
            "The AI request failed. Please try again. "
            "The free model may temporarily be unavailable.",
            502
        )

# --------------------------------------------------
# Start the learning plan
# --------------------------------------------------

@app.route("/begin-study", methods=["POST"])
def begin_study():
    subject = request.form.get("subject", "").strip()
    plan = request.form.get("plan", "").strip()

    if not plan:
        return (
            "Learning plan is missing. Please generate it again.",
            400
        )

    # Extract numbered topic headings from Markdown.
    # Example: ## Topic 1: Introduction to Python
    headings = re.findall(
        r"(?m)^\s*#{1,6}\s*(?:Topic\s*)?(\d+)\s*[:.)-]\s*(.+?)\s*$",
        plan,
        flags=re.IGNORECASE
    )

    topics = [
        {
            "number": int(number),
            "title": title.strip().strip("*# ")
        }
        for number, title in headings
    ]

    # Fallback for plans that use numbered list items instead
    # of Markdown topic headings.
    if not topics:
        items = re.findall(
            r"(?m)^\s*(?:\*\*)?(\d+)[.)]\s+(.+?)\s*(?:\*\*)?\s*$",
            plan
        )

        topics = [
            {
                "number": int(number),
                "title": title.strip().strip("*# ")
            }
            for number, title in items
        ]

    if not topics:
        return (
            "The learning plan has no recognizable numbered topics. "
            "Please generate the plan again.",
            400
        )

    return render_template(
        "lesson.html",
        subject=subject or "Your Study Plan",
        topic=topics[0]["title"],
        number=1,
        topics=topics,
        plan=plan
    )


# --------------------------------------------------
# Career Profile Matcher
# --------------------------------------------------

SKILL_CATALOG = [
    "Python", "C", "Java", "JavaScript", "HTML", "CSS",
    "React", "Node.js", "Flask", "SQL", "MongoDB",
    "Git", "REST APIs", "Data Structures", "Algorithms",
    "Pandas", "NumPy", "Machine Learning", "Deep Learning",
    "Statistics", "Data Visualization", "Linux", "Docker",
    "Cloud Computing", "CI/CD", "Networking",
    "Cybersecurity", "Linux Security", "Testing",
    "Selenium", "Communication", "Problem Solving"
]

# Natural-language terms mapped to skills in our catalog.
SKILL_ALIASES = {
    "Python": ["python", "python programming"],
    "C": [" c language", "c programming", " c "],
    "Java": ["java", "java programming"],
    "JavaScript": ["javascript", "js"],
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3", "styling websites"],
    "React": ["react", "react.js", "reactjs"],
    "Node.js": ["node.js", "nodejs", "node js"],
    "Flask": ["flask"],
    "SQL": ["sql", "mysql", "postgresql", "postgres"],
    "MongoDB": ["mongodb", "mongo db"],
    "Git": ["git", "github", "version control"],
    "REST APIs": ["rest api", "rest apis", "api development", "apis"],
    "Data Structures": ["data structures", "dsa"],
    "Algorithms": ["algorithms", "algorithm design"],
    "Pandas": ["pandas"],
    "NumPy": ["numpy", "numerical python"],
    "Machine Learning": ["machine learning", "ml"],
    "Deep Learning": ["deep learning", "neural networks"],
    "Statistics": ["statistics", "statistical analysis"],
    "Data Visualization": ["data visualization", "power bi", "tableau"],
    "Linux": ["linux", "ubuntu", "bash", "shell scripting"],
    "Docker": ["docker", "containers"],
    "Cloud Computing": ["cloud computing", "aws", "azure", "gcp"],
    "CI/CD": ["ci/cd", "continuous integration", "continuous deployment"],
    "Networking": ["networking", "tcp/ip", "computer networks"],
    "Cybersecurity": ["cybersecurity", "cyber security", "ethical hacking"],
    "Linux Security": ["linux security", "penetration testing", "pentesting"],
    "Testing": ["software testing", "manual testing", "test cases"],
    "Selenium": ["selenium", "browser automation"],
    "Communication": ["communication", "team communication"],
    "Problem Solving": ["problem solving", "problem-solving", "logical thinking"]
}

CAREER_ROLES = [
    {
        "name": "Full Stack Developer",
        "category": "Web Development",
        "description": "Build both the user interface and server-side parts of web applications.",
        "skills": ["HTML", "CSS", "JavaScript", "React", "Node.js", "SQL", "Git", "REST APIs"],
        "icon": "🌐"
    },
    {
        "name": "Frontend Developer",
        "category": "Web Development",
        "description": "Create accessible, responsive and interactive user interfaces.",
        "skills": ["HTML", "CSS", "JavaScript", "React", "Git"],
        "icon": "🎨"
    },
    {
        "name": "Python Developer",
        "category": "Software Development",
        "description": "Build applications, scripts, backend services and automation tools with Python.",
        "skills": ["Python", "Flask", "SQL", "Git", "REST APIs", "Problem Solving"],
        "icon": "🐍"
    },
    {
        "name": "Backend Developer",
        "category": "Software Development",
        "description": "Develop APIs, business logic, databases and server-side services.",
        "skills": ["Python", "Node.js", "SQL", "REST APIs", "Git", "Linux"],
        "icon": "⚙️"
    },
    {
        "name": "Data Analyst",
        "category": "Data & Analytics",
        "description": "Use data to identify patterns, answer questions and support decisions.",
        "skills": ["Python", "SQL", "Pandas", "NumPy", "Statistics", "Data Visualization"],
        "icon": "📊"
    },
    {
        "name": "AI / ML Engineer",
        "category": "Artificial Intelligence",
        "description": "Develop and evaluate machine-learning systems and AI-powered applications.",
        "skills": ["Python", "NumPy", "Pandas", "Statistics", "Machine Learning", "Deep Learning"],
        "icon": "🤖"
    },
    {
        "name": "DevOps Engineer",
        "category": "Cloud & Infrastructure",
        "description": "Automate software delivery and help applications run reliably in production.",
        "skills": ["Linux", "Git", "Docker", "Cloud Computing", "CI/CD", "Networking"],
        "icon": "☁️"
    },
    {
        "name": "Cybersecurity Analyst",
        "category": "Cybersecurity",
        "description": "Help identify security weaknesses, investigate threats and protect systems.",
        "skills": ["Networking", "Linux", "Cybersecurity", "Linux Security", "Python"],
        "icon": "🛡️"
    },
    {
        "name": "QA Automation Engineer",
        "category": "Quality Engineering",
        "description": "Test applications and automate checks to improve software quality.",
        "skills": ["Python", "Testing", "Selenium", "Git", "JavaScript"],
        "icon": "🧪"
    },
    {
        "name": "Java Developer",
        "category": "Software Development",
        "description": "Develop applications and backend services using Java.",
        "skills": ["Java", "SQL", "Data Structures", "Algorithms", "Git"],
        "icon": "☕"
    }
]


def normalize_skills(selected_skills, description):
    """Combine selected skills and skills detected in the description."""
    found = set()

    valid_selected = set(SKILL_CATALOG)
    for skill in selected_skills:
        if skill in valid_selected:
            found.add(skill)

    text = " " + description.lower() + " "

    for skill, aliases in SKILL_ALIASES.items():
        for alias in aliases:
            alias_text = alias.lower().strip()

            # Match phrases and whole words rather than random substrings.
            if alias_text and re.search(
                r"(?<!\w)" + re.escape(alias_text) + r"(?!\w)",
                text
            ):
                found.add(skill)
                break

    return found


@app.route("/career", methods=["GET", "POST"])
def career():
    results = []
    detected_skills = []
    selected_skills = []
    description = ""
    submitted = request.method == "POST"

    if submitted:
        # Get the skills selected by the user.
        selected_skills = request.form.getlist("skills")
        print("FORM SKILLS RECEIVED:", selected_skills)

        # Get the user's written skill description.
        description = request.form.get(
            "skill_description", ""
        ).strip()

        # Detect and normalize skills from both inputs.
        detected = normalize_skills(
            selected_skills,
            description
        )
        print("Selected skills:", selected_skills)
        print("Description:", description)
        print("Detected skills:", detected)
        print("Number of career roles:", len(CAREER_ROLES))

        detected_skills = sorted(detected)

        # Generate career profiles if skills were detected.
        if detected:
            for role in CAREER_ROLES:
                required = set(role.get("skills", []))

                # Avoid division by zero for incomplete role data.
                if not required:
                    continue

                matched = sorted(required & detected)
                missing = sorted(required - detected)

                score = round(
                    len(matched) / len(required) * 100
                )

                if score >= 70:
                    eligibility = "Strong match"
                elif score >= 40:
                    eligibility = "Developing match"
                else:
                    eligibility = "Skills to build"

                if matched:
                    results.append({
                        **role,
                        "score": score,
                        "matched": matched,
                        "missing": missing,
                        "eligibility": eligibility
                        })

            # Rank profiles by match score, highest first.
            results.sort(
                key=lambda item: (
                    item["score"],
                    len(item["matched"])
                ),
                reverse=True
            )

            # Display the six most relevant profiles.
            results = results[:6]

    return render_template(
        "career.html",
        skill_catalog=SKILL_CATALOG,
        selected_skills=selected_skills,
        description=description,
        detected_skills=detected_skills,
        results=results,
        submitted=submitted
    )

# --------------------------------------------------
# Run the application
# --------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)