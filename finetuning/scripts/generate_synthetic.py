"""Generate synthetic job vacancies via gpt-4o-mini to create fine-tuning training data."""

import json
import logging
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError, APIError

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_FILE = Path("finetuning/data/synthetic_examples.jsonl")

SYSTEM_PROMPT = (
    "You are a structured data extraction assistant. Extract job vacancy information "
    "into a strict JSON format. Always return valid JSON only, no explanation."
)

EXTRACTION_SCHEMA = """{
  "title": "job title string",
  "stack": ["array of specific technologies/tools/languages/frameworks"],
  "level": "junior | middle | senior | lead | unknown",
  "salary_from": <minimum salary as number or null>,
  "currency": "RUB | USD | EUR | null",
  "remote": "true | false | hybrid | unknown",
  "location": "city string or null",
  "experience_years_min": <number or null>,
  "experience_years_required": "normal | inflated | unknown"
}"""

# Individual vacancy specs: (role, level, salary_instruction, remote, stack, lang, inflated)
VACANCY_SPECS = [
    # Python/Backend — русский
    ("Python Backend Developer", "junior", "120000-180000 RUB", "true", "Python, Django, PostgreSQL, Redis", "ru", False),
    ("Django Developer", "junior", "not specified", "hybrid", "Python, Flask, MySQL", "ru", False),
    ("FastAPI разработчик", "middle", "200000-280000 RUB", "true", "Python, FastAPI, PostgreSQL, Docker", "ru", False),
    ("Python Developer", "middle", "250000-320000 RUB", "hybrid", "Python, Django, Celery, RabbitMQ, Redis", "ru", False),
    ("Backend разработчик", "senior", "350000-500000 RUB", "true", "Python, FastAPI, Kubernetes, PostgreSQL", "ru", False),
    ("Python Tech Lead", "lead", "not specified", "hybrid", "Python, Django, microservices, Kafka", "ru", False),
    # Python/Backend — english
    ("Python Backend Engineer", "middle", "3000-5000 USD", "true", "Python, FastAPI, PostgreSQL, Docker", "en", False),
    ("Senior Python Engineer", "senior", "5000-8000 USD", "true", "Python, FastAPI, Kubernetes, PostgreSQL", "en", False),
    ("Backend Lead", "lead", "not specified", "false", "Python, Go, gRPC, Redis", "en", False),
    ("Python Developer", "junior", "not specified", "false", "Python, Django, PostgreSQL", "en", False),
    # Frontend
    ("Frontend Developer", "middle", "200000-300000 RUB", "hybrid", "React, TypeScript, Redux, GraphQL", "ru", False),
    ("React разработчик", "junior", "not specified", "true", "JavaScript, Vue.js, HTML, CSS", "ru", False),
    ("Vue.js Developer", "middle", "2500-4000 USD", "true", "Vue 3, TypeScript, Vite, Pinia", "en", False),
    ("Senior Frontend Engineer", "senior", "400000-550000 RUB", "true", "React, TypeScript, Next.js, GraphQL", "ru", False),
    ("Frontend Lead", "lead", "5000-9000 USD", "hybrid", "React, TypeScript, Webpack, Node.js", "en", False),
    # DevOps/Infra
    ("DevOps Engineer", "middle", "280000-380000 RUB", "true", "Kubernetes, Terraform, AWS, Helm", "ru", False),
    ("Platform Engineer", "senior", "not specified", "false", "Docker, Ansible, GitLab CI, Prometheus", "ru", False),
    ("SRE", "senior", "6000-9000 USD", "true", "GCP, Terraform, Kubernetes, Python", "en", False),
    ("DevOps Lead", "lead", "8000-12000 USD", "true", "Kubernetes, Terraform, AWS, Python, Grafana", "en", False),
    ("Cloud Engineer", "middle", "350000-450000 RUB", "hybrid", "AWS, Terraform, Docker, CI/CD", "ru", False),
    # Data Science / ML
    ("Data Scientist", "middle", "250000-350000 RUB", "hybrid", "Python, scikit-learn, pandas, SQL", "ru", False),
    ("ML Engineer", "senior", "400000-600000 RUB", "true", "Python, PyTorch, MLflow, Kubeflow", "en", False),
    ("Data Analyst", "junior", "not specified", "hybrid", "Python, SQL, Tableau, pandas", "ru", False),
    ("Data Engineer", "senior", "8000-12000 USD", "true", "Python, Spark, Databricks, dbt", "en", False),
    ("ML Lead", "lead", "not specified", "true", "Python, PyTorch, Kubernetes, MLflow", "en", False),
    # PHP
    ("PHP Backend Developer", "junior", "100000-150000 RUB", "true", "PHP, Laravel, MySQL, Redis", "ru", False),
    ("Laravel разработчик", "middle", "200000-280000 RUB", "hybrid", "PHP, Laravel, PostgreSQL, Vue.js", "ru", False),
    ("Symfony Developer", "middle", "not specified", "false", "PHP, Symfony, MySQL, Docker", "en", False),
    ("PHP Lead", "lead", "350000-500000 RUB", "hybrid", "PHP, Laravel, Kubernetes, Redis", "ru", False),
    # Mobile
    ("iOS Developer", "middle", "300000-450000 RUB", "hybrid", "Swift, SwiftUI, Xcode, CoreData", "ru", False),
    ("Android Developer", "senior", "not specified", "true", "Kotlin, Jetpack Compose, Coroutines", "ru", False),
    ("Mobile Lead", "lead", "7000-12000 USD", "true", "Swift, Kotlin, React Native, CI/CD", "en", False),
    ("Flutter Developer", "middle", "250000-370000 RUB", "true", "Flutter, Dart, Firebase, REST", "ru", False),
    # QA / Testing
    ("QA Engineer", "junior", "not specified", "true", "Selenium, Python, Pytest", "ru", False),
    ("QA Automation Engineer", "middle", "200000-300000 RUB", "hybrid", "Python, Selenium, Appium, Jenkins", "en", False),
    ("MLOps Engineer", "senior", "4000-6000 USD", "true", "Python, Airflow, MLflow, Docker", "en", False),
    # Edge cases — inflated requirements
    ("Senior Python Developer", "senior", "negotiable", "unknown", "Python", "ru", True),
    ("Lead Backend Engineer", "lead", "not specified", "hybrid", "Python, Kubernetes", "en", True),
    ("Full Stack Developer", "middle", "negotiable", "false", "", "ru", True),
    # Additional diversity
    ("Go Developer", "middle", "300000-400000 RUB", "true", "Go, gRPC, PostgreSQL, Docker", "ru", False),
    ("Rust Engineer", "senior", "7000-11000 USD", "true", "Rust, WebAssembly, Linux, C++", "en", False),
    ("Java Backend Developer", "middle", "250000-350000 RUB", "hybrid", "Java, Spring Boot, PostgreSQL, Kafka", "ru", False),
    ("Node.js Developer", "middle", "3000-5000 USD", "true", "Node.js, TypeScript, PostgreSQL, Redis", "en", False),
    ("Staff Engineer", "lead", "15000-20000 USD", "true", "Python, Go, Kubernetes, Terraform", "en", False),
    ("Database Administrator", "senior", "not specified", "hybrid", "PostgreSQL, MySQL, Redis, MongoDB", "ru", False),
    ("Golang разработчик", "junior", "150000-200000 RUB", "true", "Go, PostgreSQL, REST", "ru", False),
    ("C++ Developer", "senior", "400000-600000 RUB", "false", "C++, Linux, CMake, Qt", "ru", False),
    ("Security Engineer", "senior", "6000-10000 USD", "true", "Python, Kubernetes, Vault, AWS", "en", False),
    ("Analytics Engineer", "middle", "280000-380000 RUB", "hybrid", "dbt, SQL, Airflow, Python", "ru", False),
    ("Product Analyst", "junior", "not specified", "hybrid", "SQL, Python, BI-инструменты", "ru", False),
    # More middle/senior to balance
    ("Ruby Developer", "middle", "2500-4000 USD", "true", "Ruby, Rails, PostgreSQL, Redis", "en", False),
    ("Scala Developer", "senior", "8000-12000 USD", "true", "Scala, Spark, Kafka, HDFS", "en", False),
    ("Kotlin Backend Developer", "middle", "300000-420000 RUB", "true", "Kotlin, Spring Boot, PostgreSQL, Docker", "ru", False),
    ("AI Engineer", "senior", "5000-9000 USD", "true", "Python, LangChain, OpenAI API, FastAPI", "en", False),
    ("LLM Engineer", "senior", "500000-700000 RUB", "true", "Python, PyTorch, LLM fine-tuning, vLLM", "ru", False),
    # Extra batch to reach 80+ total
    ("Python разработчик", "junior", "not specified", "true", "Python, Django, SQLite", "ru", False),
    ("Senior Go Engineer", "senior", "6000-9000 USD", "true", "Go, Kubernetes, gRPC, PostgreSQL", "en", False),
    ("Elixir Developer", "middle", "4000-6000 USD", "true", "Elixir, Phoenix, PostgreSQL, Redis", "en", False),
    ("React Native Developer", "middle", "280000-380000 RUB", "hybrid", "React Native, TypeScript, Firebase", "ru", False),
    ("Fullstack Python+React", "middle", "250000-350000 RUB", "true", "Python, FastAPI, React, PostgreSQL", "ru", False),
    ("Data Platform Engineer", "senior", "7000-11000 USD", "true", "Python, Spark, dbt, Snowflake, Airflow", "en", False),
    ("Infrastructure Engineer", "middle", "350000-470000 RUB", "hybrid", "Kubernetes, Terraform, GCP, Python", "ru", False),
    ("Embedded Developer", "senior", "400000-550000 RUB", "false", "C, C++, Linux, RTOS, CMake", "ru", False),
    ("Test Automation Lead", "lead", "not specified", "true", "Python, Selenium, Playwright, Jenkins, Allure", "en", False),
    ("Site Reliability Engineer", "middle", "5000-7000 USD", "true", "Linux, Python, Prometheus, Grafana, Kubernetes", "en", False),
    ("Аналитик данных", "junior", "130000-180000 RUB", "hybrid", "SQL, Python, Excel, Power BI", "ru", False),
    ("NLP Engineer", "senior", "8000-12000 USD", "true", "Python, HuggingFace, PyTorch, NLP, LLM", "en", False),
    ("Backend Go разработчик", "middle", "280000-380000 RUB", "true", "Go, PostgreSQL, Kafka, Docker", "ru", False),
    ("Senior Android Developer", "senior", "not specified", "hybrid", "Kotlin, Android SDK, Jetpack, Room, Coroutines", "ru", False),
    ("Devops/Platform Lead", "lead", "10000-15000 USD", "true", "Kubernetes, Terraform, AWS, Python, ArgoCD", "en", False),
    ("Computer Vision Engineer", "senior", "6000-10000 USD", "true", "Python, OpenCV, PyTorch, CUDA", "en", False),
    ("TypeScript Backend Developer", "middle", "3500-5500 USD", "true", "TypeScript, Node.js, NestJS, PostgreSQL", "en", False),
    ("Аналитик BI", "middle", "200000-300000 RUB", "hybrid", "SQL, Power BI, Tableau, Python", "ru", False),
    ("Системный администратор", "middle", "not specified", "false", "Linux, Bash, Ansible, Docker, Nginx", "ru", False),
    ("Cloud Architect", "lead", "12000-20000 USD", "true", "AWS, Azure, Terraform, Kubernetes, Python", "en", False),
    ("Старший разработчик C#", "senior", "350000-500000 RUB", "hybrid", "C#, .NET, ASP.NET, PostgreSQL, Redis", "ru", False),
    ("React Developer", "junior", "150000-200000 RUB", "true", "JavaScript, React, HTML, CSS", "ru", False),
    ("Machine Learning Researcher", "senior", "8000-14000 USD", "true", "Python, PyTorch, JAX, CUDA, HuggingFace", "en", False),
    ("Технический директор / CTO", "lead", "not specified", "hybrid", "Python, Kubernetes, AWS, PostgreSQL", "ru", False),
    ("Senior iOS Engineer", "senior", "5000-8000 USD", "true", "Swift, UIKit, SwiftUI, XCTest", "en", False),
    ("Разработчик игр (Unity)", "middle", "250000-350000 RUB", "true", "C#, Unity, Shaders, Git", "ru", False),
]


GENERATION_PROMPT = """Generate a realistic job vacancy text for the following position.

Role: {role}
Level: {level}
Salary: {salary_note}
Remote: {remote}
Stack: {stack}
Language: {lang}
Length: 150-400 words
Style: realistic Russian/international job board posting{inflated_note}

Then provide the correct JSON extraction following this schema:
{schema}

Return ONLY this JSON object (no markdown, no explanation):
{{"vacancy_text": "<full vacancy text>", "extraction": <json object>}}"""


def build_prompt(spec: tuple) -> str:
    """Build generation prompt for a single vacancy spec."""
    role, level, salary, remote, stack, lang, inflated = spec
    if salary == "not specified":
        salary_note = "do not include salary information"
    elif salary == "negotiable":
        salary_note = "salary is vague: use 'обсуждается' or 'competitive' or 'по результатам интервью'"
    else:
        salary_note = f"include salary range: {salary}"
    inflated_note = (
        "\nIMPORTANT: Make experience requirements clearly inflated vs market "
        "(e.g. require 6-8+ years for a role where 3-4 would be standard). "
        "Set experience_years_required='inflated' in the extraction."
    ) if inflated else ""
    stack_str = stack if stack else "not specified — leave stack array empty"
    return GENERATION_PROMPT.format(
        role=role, level=level, salary_note=salary_note, remote=remote,
        stack=stack_str, lang=lang, inflated_note=inflated_note, schema=EXTRACTION_SCHEMA,
    )


def call_openai_with_retry(client: OpenAI, prompt: str, max_retries: int = 3) -> str:
    """Call gpt-4o-mini with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1500,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content or ""
        except RateLimitError:
            wait = 2 ** attempt * 5
            logger.warning("Rate limit, waiting %ds (attempt %d/%d)", wait, attempt + 1, max_retries)
            time.sleep(wait)
        except APIError as e:
            wait = 2 ** attempt * 2
            logger.warning("API error: %s, waiting %ds (attempt %d/%d)", e, wait, attempt + 1, max_retries)
            if attempt == max_retries - 1:
                raise
            time.sleep(wait)
    raise RuntimeError("Max retries exceeded")


def make_record(vacancy_text: str, extraction: dict) -> dict:
    """Build a JSONL messages record."""
    if isinstance(extraction.get("remote"), bool):
        extraction["remote"] = str(extraction["remote"]).lower()
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": vacancy_text},
            {"role": "assistant", "content": json.dumps(extraction, ensure_ascii=False)},
        ]
    }


def main() -> None:
    """Generate synthetic examples and save to synthetic_examples.jsonl."""
    client = OpenAI()
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    saved = 0
    errors = 0

    with OUTPUT_FILE.open("w", encoding="utf-8") as out:
        for i, spec in enumerate(VACANCY_SPECS, 1):
            role = spec[0]
            logger.info("Vacancy %d/%d: %s...", i, len(VACANCY_SPECS), role)
            prompt = build_prompt(spec)
            try:
                raw = call_openai_with_retry(client, prompt)
                data = json.loads(raw)
                vacancy_text = data.get("vacancy_text", "")
                extraction = data.get("extraction", {})
                if not vacancy_text or not extraction:
                    logger.warning("Vacancy %d: empty response, skipping", i)
                    errors += 1
                    continue
                record = make_record(vacancy_text, extraction)
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                saved += 1
            except Exception as e:
                logger.error("Vacancy %d (%s): %s", i, role, e)
                errors += 1

    print(f"Saved: {saved} synthetic examples → {OUTPUT_FILE}")
    print(f"Errors: {errors}")


if __name__ == "__main__":
    main()
