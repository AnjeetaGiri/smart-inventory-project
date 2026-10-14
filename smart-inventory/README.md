# Smart Inventory

A small inventory dashboard built with FastAPI, Angular, and PostgreSQL. The repository is arranged so the backend tests run before the container is built or deployed, and the Amplify build runs frontend tests before the production build.

## Project layout

- `backend/app`: API routes, database connection, validation models, and token/password helpers.
- `backend/scripts/seed.py`: creates the schema and a sample user/data.
- `backend/tests`: backend tests.
- `frontend/src/app`: standalone Angular dashboard, login form, product table, movement modal, and HTTP auth interceptor.
- `.github/workflows/backend.yml`: backend lint, test, image build, ECR push, and ECS deployment jobs.
- `amplify.yml`: frontend test/build order.

## Run locally

Prerequisites: Python 3.11+, Node.js compatible with Angular 20, npm, and PostgreSQL 15.

1. Create a PostgreSQL database named `smartinventory` and a user that can create tables.
2. In a terminal:
   ```bash
   cd backend
   python -m venv .venv
   # Windows: .venv\\Scripts\\activate
   # macOS/Linux: source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Set `DATABASE_URL` to your PostgreSQL connection string and set `JWT_SECRET` to a long random value. For example, in PowerShell:
   ```powershell
   $env:DATABASE_URL="postgresql://smartinventory_user:your-password@localhost:5432/smartinventory"
   $env:JWT_SECRET="use-a-long-random-local-secret"
   $env:CORS_ORIGINS="http://localhost:4200"
   python scripts/seed.py
   uvicorn app.main:app --reload --port 8000
   ```
4. In another terminal:
   ```bash
   cd frontend
   npm install
   npm start
   ```
5. Open `http://localhost:4200` and sign in with `testuser` / `TestPass123!` (created by the seed script).
6. Run `npm install` in `frontend` and commit the generated `package-lock.json` before connecting Amplify. The build environment used to prepare this ZIP could not reach the npm registry, so the lockfile could not be generated here; Amplify's required `npm ci` step will not run until you commit it.

Do not use the sample JWT secret or test password for a real deployment. Do not commit `.env` files, database credentials, access keys, or `AWS_ACCESS.md`.

## API endpoints

- `GET /health`
- `POST /api/auth/token`
- `POST /api/auth/refresh`
- `GET /api/products?page=1&page_size=10&search=&sort=name&order=asc`
- `GET /api/products/{id}/stock`
- `POST /api/movements`
- `GET /api/products/{id}/movements`
- `GET /api/reports/reorder` (Bearer access token required)

Interactive API docs are available at `/docs` while the API is running.

## Backend checks

```bash
cd backend
ruff check app scripts tests
pytest
```

The CI workflow deliberately makes `test` depend on `lint`, and `build` depend on `test`. ECR push depends on image build; ECS deploy depends on push. Pull requests run lint and tests but do not publish/deploy images.

## AWS deployment outline (ap-south-1)

This repository does not create resources automatically. Create the resources in your own AWS account and verify every setting before submitting:

1. Create a VPC with public subnets for the ALB and private subnets for ECS tasks and RDS. Place ECS and RDS in the same VPC.
2. Create a private PostgreSQL 15 RDS instance named `smartinventory`. Disable public accessibility. Its security group should allow port 5432 only from the ECS task security group.
3. Store DB connection details in Secrets Manager. Configure the ECS task definition to inject the secret at runtime. Keep the secret out of source, image layers, and logs. Set `DATABASE_URL` or the `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` environment values using ECS secret references.
4. Create an ECR repository, an ECS Fargate cluster/service, an ALB and target group forwarding to container port 8000. Configure `/health` as the health check. ALB inbound port 80; ECS inbound only from the ALB security group.
5. Create an ECS task execution role with only the required ECR pull, Secrets Manager read, and CloudWatch Logs permissions. Add a separate task role only if the application needs AWS API access.
6. Configure GitHub Actions OIDC in IAM with a trust policy restricted to this repository and the main branch. Add repository Actions variables/secrets: `AWS_GITHUB_ACTIONS_ROLE_ARN`, `ECR_REGISTRY`, `ECR_REPOSITORY`, `ECS_CLUSTER`, `ECS_SERVICE`, and `ECS_TASK_FAMILY`. No long-lived AWS access keys should be used by CI.
7. Run the seed script from a trusted environment that can reach the private RDS instance. Do not open RDS to the internet just to seed it.
8. Connect the GitHub repository to Amplify. Set `API_URL` in Amplify Console to the ALB URL. Configure the Angular environment replacement/build process to use that value before building; see the note below.
9. Validate `/health`, login, product search, movement logging, reorder report, security groups, task health, pipeline history, and Amplify HTTPS before sharing the app.

### Important deployment notes

- `frontend/src/environments/environment.ts` is a local default. The Amplify pre-build phase writes this file from the `API_URL` environment variable so Angular embeds the configured ALB URL at build time. Do not commit credentials; the API URL itself is not a secret.
- ECS secret injection should be configured in the task definition's `secrets` array (the standard ECS field). The assignment mentions `secretsFrom`, but the standard ECS task-definition property is `secrets`.
- The supplied workflow is a starting point and needs your actual AWS resource names and OIDC role configuration. Verify the task definition's first container is the API container before using the deploy job.
- The CI workflow currently tests the health route without a live DB; expand the integration tests for database routes before production use. Do not claim the project has passed AWS deployment until you run it in your account.
- Use HTTPS for production API traffic if possible (for example, an HTTPS ALB listener with an ACM certificate). The assignment specifically asks for Amplify HTTPS; its default domain provides that for the frontend.

## Submission security reminder

The assignment asks for a dedicated read-only review IAM user and an `AWS_ACCESS.md` file sent separately. Never create or send root credentials. Review the requested policies carefully: `SecretsManagerReadWrite` is broader than read-only despite the document's description, so consider asking the reviewer whether a narrower policy is acceptable before granting it. Never commit the access file to GitHub.
