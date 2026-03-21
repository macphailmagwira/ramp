# OpenAPI to GraphQL Resolver Generator

Automatically generate GraphQL resolvers and AWS AppSync VTL templates from your FastAPI OpenAPI schema.

## Quick Start

```bash
# 1. Generate resolver configurations from OpenAPI
cd terraform/modules/appsync
node generate-from-openapi.js

# 2. Generate VTL templates for AppSync
node generate-vtl.js

# 3. Deploy to AWS
terraform plan
terraform apply
```

## Steps

### 1. Add Endpoint to FastAPI

Add your endpoint with an `operation_id`:

```python
@router.post("/machines", operation_id="createMachine", status_code=201)
async def create_machine(machine: MachineCreate):
    return await service.create_machine(machine)
```

### 2. Add to GraphQL Schema

**⚠️ CRITICAL:** Add matching query/mutation to `terraform/modules/appsync/schema.graphql`

The GraphQL field name **MUST MATCH** the FastAPI `operation_id`:

```graphql
type Mutation {
  createMachine(input: MachineInput!): Machine
}
```

**Naming must match exactly:**

- FastAPI: `operation_id="createMachine"`
- GraphQL: `createMachine(input: ...)`

### 3. Generate Resolvers

```bash
cd terraform/modules/appsync
node generate-from-openapi.js
node generate-vtl-resolvers.js
```

### 4. Deploy

```bash
terraform plan
terraform apply
```

## Local Testing (Optional)

Test your GraphQL API locally before deploying:

```bash
cd apps/api-main/graphql
node server.js
# Visit http://localhost:4000
```

## Add tests to Appsync test suite

Appsync tests are located in apps/api-main/tests/appsync:

```bash
cd apps/api-main/
poetry run pytest ./tests/appsync/
```
