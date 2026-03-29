# Architecture Review Plan (Auto-Plan Smoke Test)

## Review Scope

This document outlines a lightweight architecture review plan for `my-virtual-team`.

## Key Review Areas

### 1. Plane Separation
- **Knowledge Plane**: Verify agent metadata, context graph freshness, and registry generation logic
- **Control Plane**: Review task lifecycle, DAG resolution, lock/approval mechanisms in `.runtime/state.db`
- **Execution Plane**: Validate AI runner routing, fast path vs multi-phase decision logic
- **Operations Plane**: Check event fan-out, GitHub bridge, and health monitoring

### 2. Critical Paths
- Bootstrap flow (`npm run bootstrap`)
- Task routing and dispatch (`runtime:task -- route/plan/start`)
- GitHub event integration (smoke tests in `github-ops.yml`)
- Context loading strategy (always/required/never refs)

### 3. Smoke Test Coverage
- Issue opened → routing decision
- Issue comment → slash command execution
- Synthetic PR → PR routing verification
- CI verification flow (`ci:verify`)

## Review Deliverables

- [ ] Plane boundary violations identified
- [ ] Dead code or unused templates flagged
- [ ] Critical path failure scenarios documented
- [ ] Smoke test gaps highlighted

## Next Steps

Review findings will be handed off to `/development` or `/strategy` for prioritization and implementation planning.

---

*This file was created by the [smoke][auto-plan] architecture review plan smoke test.*
