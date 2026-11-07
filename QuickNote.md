# Quick Note

### Development effort

Approximately **40 hours** were dedicated to the development, testing, evaluation and documentation of the Finance Spend Intelligence Assistant.

### Development approach

PostgreSQL and Next.js were selected partly because of my previous experience with these technologies, allowing me to focus on the application functionality and architecture.

A free ChatGPT account was used as an auxiliary development tool for implementation support, troubleshooting, code review and exploring alternative approaches. Suggestions were reviewed, adapted and tested before being incorporated into the project.

### Scope and trade-offs

The main priority was delivering a functional end-to-end solution with reliable financial data retrieval, controlled LLM routing, a usable interface and a comparative evaluation framework.

Some aspects were deliberately simplified to stay within the available development time:

- **Data processing:** Pandas and CSV were retained because the dataset contains only 140 invoices.
- **LLM integration:** Procurement policy is provided directly as context rather than implementing a dedicated RAG pipeline.
- **Evaluation:** A custom benchmark and LLM-as-a-judge approach were implemented. RAGAS integration was postponed to prioritise model comparison and application testing.
- **Guardrails:** The implementation covers basic routing outcomes and empty-answer validation, rather than comprehensive semantic verification.

### Remaining improvements

The most relevant areas for further development are:

- Expand the benchmark with additional edge cases and human-reviewed examples.
- Validate and calibrate the LLM judge against expert assessments.
- Add semantic evaluation of clarification handling.
- Explore RAGAS if a dedicated document retrieval pipeline is introduced.
- Improve automated testing, error handling and monitoring.
- Add richer financial visualisations and analytical capabilities.

The prototype demonstrates the main application workflow and provides an initial comparison of four LLMs. Further work would focus on improving evaluation coverage, reliability and analytical capabilities.