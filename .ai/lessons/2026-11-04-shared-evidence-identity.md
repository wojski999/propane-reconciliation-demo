# Shared evidence must retain the comparison dimension

A collision guard exposed valid many-to-one inputs that single-entity tests missed:
several operational mappings can reference one journal/account, and several batches
can reference one deposit. Related evidence varies, so identical journal/deposit
primary keys are insufficient to identify independent findings.

Include the varying mapping/batch key in primary evidence, or evaluate a truly
batch-independent comparison once. Keep the explicit conflicting-ID failure for
actual engine defects; never restore silent overwrites. Prove accepted data shapes
through raw generated file mutation and real ingestion, with two/three-way reuse,
precise expected values, retained unrelated findings, evidence resolution and
invariance under raw/detached record reordering. Coverage alone did not catch this.
