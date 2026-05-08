# Contributing to TriageAI

Thank you for your interest in contributing to TriageAI!

## Development Setup

### Prerequisites

- Node.js 20+
- PostgreSQL 15+
- Redis 7+
- Docker (optional, for containerized development)

### Getting Started

1. Clone the repository:
   ```bash
   git clone https://github.com/pdaxt/triage-ai.git
   cd triage-ai
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Set up environment:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

4. Start databases (using Docker):
   ```bash
   docker-compose up -d postgres redis
   ```

5. Run migrations:
   ```bash
   npm run db:migrate
   ```

6. Start development:
   ```bash
   npm run dev
   ```

## Project Structure

```
triage-ai/
├── apps/
│   ├── web/           # React frontend
│   └── api/           # Node.js backend
├── packages/
│   ├── triage-engine/ # Core AI triage logic
│   ├── symptom-parser/# NLP symptom extraction
│   └── shared/        # Shared types, utilities
└── docs/              # Documentation
```

## Code Standards

- **TypeScript:** All code must be TypeScript with strict mode
- **Formatting:** Run `npm run format` before committing
- **Linting:** Run `npm run lint` - must pass with no errors
- **Tests:** Add tests for new features, maintain >80% coverage

## AI-Agents-First Development

This project uses an AI-agents-first development methodology:

1. **Rapid iteration:** Features built in hours, not weeks
2. **Documentation-driven:** Write specs before code
3. **AI-assisted testing:** Use AI to generate edge case tests

When contributing:
- Write clear, specific commit messages
- Document your changes in relevant `.md` files
- Include AI-generated test cases for edge cases

## Pull Request Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Run tests: `npm test`
5. Push and create a PR
6. Wait for review

## Healthcare Compliance

TriageAI handles sensitive healthcare data. When contributing:

- **Never log PHI** (Protected Health Information)
- **Always encrypt** sensitive data at rest and in transit
- **Audit trail:** All clinical decisions must be logged
- **Test data:** Use synthetic data only, never real patient data

## Questions?

Open an issue or reach out to the maintainers.
