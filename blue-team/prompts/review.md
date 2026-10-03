Review the implementation of task {task} independently. The diff is below. You may read files and run the approved tests, but do not edit anything; required fixes go back to the implementer.

The diff may be trimmed (it then ends with "[diff trimmed]"). A review of a partial change is not a review. When it is trimmed, or when a changed file is long, read every changed file in full with your file tools before you give a verdict. Begin your summary by naming each file you read in full and any line ranges you did not read. If you could not read all of a changed file, say so and do not approve.

Check, in order: security and isolation (credentials, ground truth, red/blue context separation, evidence integrity), correctness against the accepted decision, whether the tests would fail if the code were wrong, and simplicity. Cite file and line in `findings`.

`verdict` is `approve`, `changes-requested`, or `security-objection` (only for a real risk; it goes to the human).
