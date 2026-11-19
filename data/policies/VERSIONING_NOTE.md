# Policy versioning demonstration

Initial active documents:
- TechNova v1.0
- DataSphere v1.0
- CloudAxis v1.0

Version update demonstration:
- TechNova v2.0 supersedes TechNova v1.0 from 1 November 2026.
- The changed rules are the booking cut-off (2 hours -> 3 hours) and ad-hoc cap (INR 800 -> INR 900).
- During ingestion, stage all v2 chunks, validate them, then atomically switch the active version.
- If ingestion fails, TechNova v1.0 must remain active.

These are fictional policies for testing. They are deliberately similar in structure and differ in key rules to test company isolation and retrieval accuracy.
