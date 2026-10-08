![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green)
![LangGraph](https://img.shields.io/badge/LangGraph-Agentic_AI-purple)
![Groq](https://img.shields.io/badge/Groq-LLM-orange)

# 🚀 ColdMail AI Pro

**An agentic AI SDR that turns a single batch of job openings into
personalized, research-backed cold emails.**

## 🚩 Problem Statement

During college placement season, the placement team may send **15--20+
job openings in a single email**.

The usual process is repetitive and time-consuming:

-   Open every JD individually
-   Understand the required skills
-   Check whether the role matches your profile
-   Find the relevant company/contact information
-   Write a separate personalized email
-   Attach the resume and verify links
-   Repeat the same process for every company

Doing this manually for every opportunity is **slow, frustrating, and
difficult to scale**, especially when new openings arrive frequently.

## 💡 Our Solution

We built **ColdMail AI Pro** to automate this entire workflow.

Instead of manually processing every JD, the user can provide the batch
of opportunities and the system:

**Extracts → Researches → Matches → Retrieves → Writes → Reviews →
Rewrites → Gets Approval → Sends**

The AI does the repetitive work while the user keeps control over the
final email.

------------------------------------------------------------------------

## 🧠 How It Works

``` text
Placement Email / Job Openings
            ↓
   Opportunity Extraction
            ↓
      Company Research
            ↓
    Resume ↔ JD Matching
            ↓
       Hybrid RAG
   (BM25 + Embeddings)
            ↓
  Personalized Email Writer
            ↓
      AI Email Review
            ↓
      Rewrite if Needed
            ↓
     Human Approval Gate
            ↓
        SMTP / Send
            ↓
        Analytics
```

### LangGraph Workflow

``` text
Research → Match → Write → Review
                         ↓
                  Rewrite / Pass
                         ↓
                  Human Approval
                    ↙        ↘
                 Pause       Send
```

------------------------------------------------------------------------

## ✨ Key Features

### 📥 Batch Job Processing

Extract multiple opportunities from one unstructured placement/recruiter
message.

### 🔎 Company Research

Researches public company pages and creates evidence that can be used
while generating the email.

### 🎯 Resume--JD Matching

Combines skill matching and semantic similarity to identify the
candidate's strongest fit.

### 🧠 Hybrid RAG

Uses **BM25 + dense embeddings** to retrieve relevant resume/profile
evidence instead of blindly passing the entire resume to the LLM.

### ✍️ Personalized Email Generation

Generates concise emails based on:

-   Job requirements
-   Relevant candidate skills/projects
-   Company research
-   Candidate profile

### ✅ AI Review + Rewrite

Each email is evaluated for personalization, clarity, grounding, quality
and potential issues. Weak emails can be routed back for rewriting.

### 🔐 Human-in-the-Loop

Emails do **not** get sent automatically after generation. The user
explicitly approves them before the external send step.

### 🔗 Safe Link Handling

Only approved/profile-provided links are retained, helping prevent
hallucinated portfolio or social links.

### 📊 Analytics

Track generated emails, sent emails, failed sends, campaign history and
personalization scores.

------------------------------------------------------------------------

## 🏗️ Architecture

``` mermaid
flowchart TD
    A[Job / Recruiter Input] --> B[Opportunity Extraction]
    B --> C[Company Research]
    B --> D[Resume-JD Matching]
    E[Candidate Profile + Resume] --> F[Hybrid RAG Retrieval]

    C --> G[Research Evidence]
    D --> H[Match Score]
    F --> I[Relevant Resume Evidence]

    G --> J[LLM Email Writer]
    H --> J
    I --> J

    J --> K[AI Review + Quality Gates]
    K -->|Rewrite| J
    K -->|Pass| L[Human Approval]

    L -->|Approved| M[SMTP Sender]
    L -->|Rejected| N[Pause]

    M --> O[Campaign Analytics]
```

------------------------------------------------------------------------

## 🛠️ Technology Stack

  Layer              Technology
  ------------------ -------------------------------------
  Frontend           HTML, CSS, Vanilla JavaScript
  Backend            FastAPI
  Agentic Workflow   LangGraph
  LLM                Groq
  Retrieval          BM25 + Sentence Transformers
  RAG                Hybrid Retrieval
  Research           HTTPX, Trafilatura, BeautifulSoup
  PDF Processing     PyMuPDF
  Database           SQLAlchemy + SQLite
  Auth               JWT + bcrypt
  Email              SMTP
  Infrastructure     Docker, Redis, PostgreSQL, ChromaDB
  Testing            Pytest

------------------------------------------------------------------------

## 🖥️ Screenshots

### Dashboard

![Dashboard]
<img width="1470" height="956" alt="dashboard" src="https://github.com/user-attachments/assets/cb95ebbf-8914-4420-9c28-5e7cfcd8159e" />


### Review & Send

![Review & Send](https://drive.google.com/file/d/1uv0VbHeENtHWzsQ-I8tjLH-8Ckn7SS8X/view?usp=sharing)

### Profile & Settings

![Profile](https://drive.google.com/file/d/1B9lf_T8Xz-jjtvtj7qNmXgbOmmD4Gp2J/view?usp=sharing)

### Analytics

![Analytics](https://drive.google.com/file/d/1SwyPl4El-GrH0pUT2jvOs9XI7PrbcVsG/view?usp=drive_link)

------------------------------------------------------------------------

## 📁 Project Structure

``` text
coldmail-ai-pro/
├── agents/
│   ├── extractor.py
│   ├── matcher.py
│   ├── researcher.py
│   ├── writer.py
│   ├── sender.py
│   ├── state.py
│   └── nodes/
├── api/
│   ├── main.py
│   └── routes/
├── services/
│   ├── llm.py
│   ├── hybrid_retrieval.py
│   ├── vectorstore.py
│   └── cache.py
├── models/
├── utils/
├── frontend/
├── tests/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

------------------------------------------------------------------------

## ⚙️ Run Locally

``` bash
git clone <your-repository-url>
cd coldmail-ai-pro

python3.11 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

Add your API key:

``` env
GROQ_API_KEY=your_groq_api_key
```

Run the application:

``` bash
uvicorn api.main:app --reload
```

Open:

``` text
http://localhost:8000
```

API docs:

``` text
http://localhost:8000/docs
```

### Docker

``` bash
docker compose up --build
```

------------------------------------------------------------------------

## 🔐 Safety

Real email sending is disabled by default:

``` env
DEMO_MODE=true
ENABLE_REAL_EMAIL_SEND=false
```

The system uses a **human approval gate**, structured validation,
evidence-grounded generation, link sanitization and regression tests
before external actions.

------------------------------------------------------------------------

## 🧪 Testing

``` bash
pytest -q
```

Tests cover extraction, matching, retrieval, workflow nodes, schemas and
email-sending safety.

------------------------------------------------------------------------

## 🎯 Why this project?

ColdMail AI Pro solves a real problem in the college placement workflow
by combining:

**Agentic AI + RAG + NLP + Semantic Matching + LLM Evaluation +
Human-in-the-Loop Automation**

The goal is not just to generate an email, but to build an end-to-end
system that can **understand opportunities, reason about fit, ground its
output in evidence, improve weak drafts, and safely assist with outreach
at scale.**

------------------------------------------------------------------------

## 👩‍💻 Author

**Kavya Gupta**

AI/ML \| Generative AI \| RAG \| AI Agents

-   GitHub: https://github.com/kavya1b1
-   LinkedIn: https://www.linkedin.com/in/its-kavya-gupta/
