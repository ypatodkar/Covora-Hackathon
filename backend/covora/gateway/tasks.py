from enum import StrEnum


class TaskType(StrEnum):
    # Nano tasks (spec §15.2)
    query_generation = "query_generation"
    company_extraction = "company_extraction"
    fact_extraction = "fact_extraction"
    people_extraction = "people_extraction"
    email_draft = "email_draft"
    handoff_reply_draft = "handoff_reply_draft"
    reply_classification = "reply_classification"
    sim_reply_writing = "sim_reply_writing"
    routing_judge = "routing_judge"
    # Super tasks
    icp_parsing = "icp_parsing"
    company_fit = "company_fit"
    contact_selection = "contact_selection"
    reply_reclassification = "reply_reclassification"
    learning_analysis = "learning_analysis"
    eval_judge = "eval_judge"
    # Embeddings (not routed)
    embedding = "embedding"


class Tier(StrEnum):
    nano = "nano"
    super = "super"


_NANO = {
    TaskType.query_generation,
    TaskType.company_extraction,
    TaskType.fact_extraction,
    TaskType.people_extraction,
    TaskType.email_draft,
    TaskType.handoff_reply_draft,
    TaskType.reply_classification,
    TaskType.sim_reply_writing,
    TaskType.routing_judge,
}
_SUPER = {
    TaskType.icp_parsing,
    TaskType.company_fit,
    TaskType.contact_selection,
    TaskType.reply_reclassification,
    TaskType.learning_analysis,
    TaskType.eval_judge,
}

TASK_TIERS: dict[TaskType, Tier] = {t: Tier.nano for t in _NANO} | {t: Tier.super for t in _SUPER}

# Reasoning on/off by default per tier (spec §15.5).
REASONING_DEFAULT: dict[Tier, bool] = {Tier.nano: False, Tier.super: True}
