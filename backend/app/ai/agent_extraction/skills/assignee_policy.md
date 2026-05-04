---
name: assignee_policy
description: Policy for recommending task assignees during extraction
---

# Assignee Recommendation Policy

After creating tasks, call `recommend_assignees` to recommend the best assignees for each task.

## Workflow

1. Call `get_assignee_skills` to retrieve the list of candidate assignees (most efficient if done before `create_tasks`).
2. For each `task_candidate_id` returned by `create_tasks`, evaluate candidates based on skills, role, and availability, then rank the top 1-3.
3. Call `recommend_assignees` exactly once, submitting all task recommendations together.

## Selection Criteria

Assignee selection criteria (in priority order):
1. **Skill match**: How well the candidate's skills match the task content
2. **Role fit**: How relevant the candidate's role is to the task type
3. **Availability**: `available` > `busy`. Do not recommend `unavailable` candidates
4. **Load balancing**: Distribute work evenly — avoid overloading a single person

## Confidence Scoring

confidence_score guidelines:
- 0.85–1.0: Skills and role are a perfect match, candidate is available
- 0.70–0.84: Partial skill match, or candidate is busy
- 0.50–0.69: Only indirect relevance
- Below 0.50: Do not recommend (exclude from the list)

## Rules

- Reasoning must be written concisely in English (1-2 sentences).
- `person_id` must be a UUID from the `get_assignee_skills` response.
- If no candidates are suitable, set `recommendations` to an empty array.
