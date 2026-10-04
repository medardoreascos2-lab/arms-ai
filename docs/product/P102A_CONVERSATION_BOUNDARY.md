# P102A MEDAR conversation integration boundary

Status: BLOCKED ON PRODUCT API CONTRACT. No conversation endpoint or send control was added.

The base contains `backend.medar.response.CognitiveResponse` with answer, status, confidence, a user-facing reasoning summary, source and memory evidence, warnings, follow-up state, and non-executable action proposals. It has no MEDAR conversation route in `backend/api`. The existing `/ai/copilot` route calls `backend.ai.conversation_engine.ConversationEngine`, a separate legacy engine. Treating that response as MEDAR would mislabel provenance and capability.

A product adapter should be designed and authorized before P102A continues. Its server boundary needs authenticated tenant/user identity, a canonical product entitlement decision, memory consent and scope, request size limits, per-user rate limits, and a response projection from `CognitiveResponse`. The projection should preserve explicit status, confidence, sources, warnings, memory references, and follow-up prompts while exposing only the user-facing reasoning summary. Action proposals must remain proposals and cannot authorize account, PAPER, LIVE, broker, or external effects. Conversation text must not enter URL parameters or content-free analytics.

The frontend should show an unavailable state until that contract exists. The product navigation currently marks MEDAR as planned. No real conversation, memory write, tool execution, or trading side effect is implemented on this track.

Decision needed: authorize a separate authenticated product API adapter over MEDAR's canonical response contract, or keep the premium MEDAR surface deferred until another track publishes that API. Do not route the product UI through legacy `/ai/copilot` by inference.
