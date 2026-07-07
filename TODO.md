# TODO - SYSTEM ROLE conversation engine integration

- [ ] Inspect existing engines needed for pipeline stages (RQU/ICE/TEE/CIE/Faiss/Diagnostic/Repair reasoning) and identify callable methods.
- [ ] Add new endpoint in `app/api/v2_routes.py` (POST /v2/system-role) that implements stages 1-13 internally.
- [ ] Ensure stages 1-9: understanding -> intent -> entity extraction -> equipment -> component -> problem detection -> parameter extraction -> missing info detection -> clarification questions (max 5).
- [ ] Ensure stages 10-12: FAISS retrieval -> graph reasoning -> repair planning, without diagnosing.
- [ ] Ensure stage 13: convert Repair Plan JSON into natural technician conversation; return conversational text only.
- [ ] Add minimal unit/integration tests hitting the new endpoint (or unit test helper) to ensure:
  - missing info path returns JSON-free conversational questions
  - retrieval/planning path returns conversational plan.
- [ ] Run test suite.
- [ ] Ensure endpoint compiles (no missing imports) and fix any lint/test failures.


