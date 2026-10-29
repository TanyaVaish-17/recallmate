"""Create a demo student with 3 subjects, 12 topics, 48 questions and 3 exams.

    cd backend
    python -m scripts.seed_demo            # create (skips if the demo user already exists)
    python -m scripts.seed_demo --reset    # delete the demo user (cascades) and recreate

It deliberately creates NO quiz history and NO predictions: those must come from real
quiz attempts you take during the demo. Demo login only (not for real use):
    email: demo@recallmate.dev    password: demo12345
"""
import argparse
from datetime import date, timedelta

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Exam, Question, QuestionOption, Subject, Topic, User

EMAIL, PASSWORD = "demo@recallmate.dev", "demo12345"

# (question, correct answer, [3 wrong answers], explanation)
DATA = {
    "Deep Learning": ("#6366F1", 5, {
        "Neural Network Basics": (2, 30, [
            ("Which activation function outputs values strictly between 0 and 1?", "Sigmoid", ["ReLU", "Tanh", "Leaky ReLU"], "Sigmoid squashes any input into (0, 1); tanh gives (-1, 1) and ReLU is unbounded above."),
            ("What does the bias term in a neuron do?", "Shifts the activation function left or right", ["Scales every input", "Prevents overfitting", "Normalises the batch"], "Bias lets the neuron fire even when all inputs are zero by shifting the decision boundary."),
            ("Which loss is standard for binary classification?", "Binary cross-entropy", ["Cosine decay", "Categorical accuracy", "Huber loss"], "Binary cross-entropy compares predicted probabilities with 0/1 labels."),
            ("A deep stack of linear layers with no non-linear activations is equivalent to:", "A single linear layer", ["A convolutional network", "A recurrent network", "A universal function approximator"], "Composition of linear maps is linear, so extra depth adds no expressive power."),
        ]),
        "Backpropagation": (3, 40, [
            ("Backpropagation computes:", "Gradients of the loss with respect to parameters using the chain rule", ["The forward-pass outputs", "The learning rate", "The number of layers"], "It applies the chain rule layer by layer from the loss backwards."),
            ("The vanishing gradient problem is most associated with:", "Saturating activations such as sigmoid in deep networks", ["ReLU in shallow networks", "Large batch sizes", "Using dropout"], "Sigmoid derivatives are at most 0.25, so products over many layers shrink towards zero."),
            ("The gradient descent update rule is:", "theta = theta - eta * gradient", ["theta = theta + eta * gradient", "theta = theta * gradient", "theta = theta - loss"], "We move against the gradient to reduce the loss."),
            ("Which technique mitigates exploding gradients?", "Gradient clipping", ["Dropout", "Data augmentation", "Early stopping"], "Clipping caps the gradient norm before the update."),
        ]),
        "Transformers and Attention": (4, 45, [
            ("In self-attention, each output is:", "A weighted sum of value vectors, with weights from softmax of query-key scores", ["A max-pool over neighbouring tokens", "A convolution over the sequence", "The previous hidden state"], "Weights come from softmax(QK^T / sqrt(d_k)) applied to V."),
            ("Why are attention scores divided by sqrt(d_k)?", "To stop large dot products saturating the softmax", ["To make the model causal", "To add positional information", "To reduce the number of heads"], "Large dot products push softmax into regions with tiny gradients."),
            ("What does a causal mask do?", "Stops a position attending to future positions", ["Hides padding tokens only", "Randomly drops attention heads", "Normalises the layer outputs"], "Scores above the diagonal are set to -inf so step t sees only steps <= t."),
            ("Why do Transformers need positional encodings?", "Self-attention on its own ignores token order", ["Embeddings are too small", "Softmax needs sorted input", "To speed up training"], "Attention is permutation-invariant without position information."),
        ]),
        "Regularization and Optimization": (3, 30, [
            ("What does dropout do during training?", "Randomly zeroes activations to reduce overfitting", ["Increases the learning rate", "Removes layers permanently", "Normalises gradients"], "It prevents co-adaptation of units."),
            ("L2 regularization adds a penalty proportional to:", "The sum of squared weights", ["The sum of absolute weights", "The number of layers", "The batch size"], "L1 uses absolute values; L2 uses squares (weight decay)."),
            ("Early stopping halts training when:", "Validation performance stops improving", ["Training loss reaches zero", "The batch size changes", "Gradients become negative"], "It limits overfitting by watching held-out data."),
            ("Adam combines:", "Momentum with per-parameter adaptive learning rates", ["Dropout with batch norm", "SGD with weight decay only", "Second-order Newton steps"], "It keeps running averages of gradients and squared gradients."),
        ]),
    }),
    "Operating Systems": ("#10B981", 9, {
        "Process Scheduling": (3, 30, [
            ("Which scheduling algorithm runs the process with the shortest next CPU burst first and is non-preemptive in its basic form?", "Shortest Job First", ["Round Robin", "Multilevel feedback queue", "Preemptive priority"], "SJF minimises average waiting time but can starve long jobs."),
            ("What is the key parameter of Round Robin scheduling?", "Time quantum", ["Priority level", "Burst length", "Page size"], "Each process runs for at most one quantum before being preempted."),
            ("Starvation in priority scheduling is usually addressed by:", "Aging", ["Increasing the quantum", "Disabling interrupts", "Swapping"], "Aging gradually raises the priority of waiting processes."),
            ("Turnaround time is:", "Completion time minus arrival time", ["Completion time minus burst time", "First response minus arrival time", "Burst time plus arrival time"], "It is the total time from submission to completion."),
        ]),
        "Deadlocks": (4, 40, [
            ("Which is NOT a necessary condition for deadlock?", "Preemption of resources", ["Mutual exclusion", "Hold and wait", "Circular wait"], "Deadlock requires NO preemption, not preemption."),
            ("The Banker's algorithm is used for:", "Deadlock avoidance", ["Page replacement", "CPU scheduling", "Disk scheduling"], "It grants a request only if the system stays in a safe state."),
            ("Circular wait can be prevented by:", "Imposing a total order on resource acquisition", ["Allowing preemption of the CPU", "Using larger pages", "Increasing the quantum"], "If everyone acquires resources in order, no cycle can form."),
            ("A state that has a safe sequence is called a:", "Safe state", ["Deadlock state", "Starved state", "Blocked state"], "A safe state guarantees every process can finish."),
        ]),
        "Memory Management": (4, 40, [
            ("A page table maps:", "Virtual page numbers to physical frame numbers", ["Files to disk blocks", "Processes to CPU cores", "Threads to stacks"], "It is the core of paged address translation."),
            ("The TLB is:", "A cache of recent page-table translations", ["A disk cache", "A CPU scheduler queue", "A swap partition"], "It avoids a page-table memory access on most references."),
            ("Belady's anomaly can occur with:", "FIFO page replacement", ["LRU page replacement", "Optimal page replacement", "Stack-based algorithms"], "With FIFO, more frames can paradoxically cause more faults."),
            ("Thrashing means:", "A process spends more time paging than executing", ["The CPU overheats", "The disk is full", "Too many threads exist"], "It happens when the working set exceeds available frames."),
        ]),
        "Process Synchronization": (3, 30, [
            ("Semaphore operations are traditionally called:", "wait (P) and signal (V)", ["push and pop", "read and write", "fork and join"], "wait decrements and may block; signal increments and may wake a waiter."),
            ("A race condition occurs when:", "The outcome depends on the timing of concurrent accesses to shared data", ["Two processes use different data", "A process runs too fast", "The CPU has multiple cores"], "Unsynchronised access to shared state makes results nondeterministic."),
            ("Which critical-section requirement says a waiting process must eventually enter?", "Bounded waiting", ["Mutual exclusion", "Progress", "Atomicity"], "Bounded waiting limits how long others can overtake a waiting process."),
            ("How does a mutex differ from a binary semaphore?", "A mutex has an owner: the thread that locked it must unlock it", ["A mutex can count above one", "A mutex never blocks", "A mutex works only across machines"], "Ownership is the key conceptual difference."),
        ]),
    }),
    "DBMS": ("#F59E0B", 14, {
        "Normalization": (3, 30, [
            ("First normal form requires:", "Atomic values in every column", ["No foreign keys", "No primary key", "Only one table"], "1NF forbids repeating groups and multi-valued cells."),
            ("Second normal form removes:", "Partial dependencies on part of a composite key", ["Transitive dependencies", "All NULL values", "Multi-valued attributes"], "Non-key attributes must depend on the whole key."),
            ("BCNF requires that for every non-trivial dependency X -> Y:", "X is a superkey", ["Y is a prime attribute", "X is a foreign key", "Y is unique"], "BCNF is a stricter version of 3NF."),
            ("The main goal of normalization is to:", "Reduce redundancy and update anomalies", ["Speed up all queries", "Increase storage use", "Remove primary keys"], "Less duplication means fewer inconsistent updates."),
        ]),
        "SQL Joins and Queries": (2, 30, [
            ("INNER JOIN returns:", "Only rows with matching keys in both tables", ["All rows from both tables", "All rows from the left table", "The Cartesian product"], "Unmatched rows are dropped."),
            ("LEFT JOIN returns:", "All left-table rows plus matches, with NULLs where none exist", ["Only matching rows", "All right-table rows", "Rows without matches only"], "The left side is preserved."),
            ("Which clause filters groups after GROUP BY?", "HAVING", ["WHERE", "ORDER BY", "LIMIT"], "WHERE filters rows before grouping; HAVING filters groups."),
            ("A CROSS JOIN of tables with 3 and 4 rows returns:", "12 rows", ["7 rows", "4 rows", "3 rows"], "It is the Cartesian product: 3 x 4."),
        ]),
        "Transactions and ACID": (4, 40, [
            ("Atomicity means a transaction's operations:", "All happen or none do", ["Run in parallel", "Run in sorted order", "Are cached in memory"], "A failed transaction is rolled back completely."),
            ("Isolation protects against:", "Concurrent transactions interfering with each other", ["Disk failure", "Syntax errors", "Duplicate tables"], "Each transaction behaves as if it ran alone."),
            ("A dirty read is:", "Reading uncommitted data from another transaction", ["Reading a deleted table", "Reading from a slow disk", "Reading NULL values"], "If that transaction rolls back, you read data that never existed."),
            ("Durability is typically implemented with:", "Write-ahead logging", ["Larger indexes", "Table partitioning", "Query caching"], "Logged commits can be replayed after a crash."),
        ]),
        "Indexing": (3, 30, [
            ("B+ tree indexes are especially good at:", "Range queries", ["Full-text translation", "Compressing rows", "Encrypting columns"], "Leaves are linked in order, so ranges are scanned sequentially."),
            ("A clustered index:", "Determines the physical order of rows", ["Is stored in a separate hash table", "Can exist many times per table", "Only speeds up inserts"], "A table can have only one physical ordering."),
            ("A downside of adding many indexes is:", "Slower writes and more storage", ["Slower reads", "Loss of primary keys", "Invalid foreign keys"], "Every insert or update must maintain each index."),
            ("A hash index is best for:", "Equality lookups", ["Range scans", "Sorting", "Prefix matching"], "Hashing gives O(1) exact matches but no ordering."),
        ]),
    }),
}


def seed(reset: bool) -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == EMAIL))
        if user and not reset:
            print(f"Demo user already exists ({EMAIL}). Use --reset to recreate.")
            return
        if user:
            db.delete(user)  # ON DELETE CASCADE removes everything they own
            db.commit()

        user = User(email=EMAIL, hashed_password=hash_password(PASSWORD), display_name="Demo Student",
                    daily_study_minutes=120, session_minutes=30)
        db.add(user)
        db.flush()

        n_q = 0
        for sname, (color, exam_in_days, topics) in DATA.items():
            subject = Subject(user_id=user.id, name=sname, color=color)
            db.add(subject)
            db.flush()
            db.add(Exam(user_id=user.id, subject_id=subject.id, title="End-semester exam",
                        exam_date=date.today() + timedelta(days=exam_in_days)))
            for tname, (difficulty, minutes, questions) in topics.items():
                topic = Topic(subject_id=subject.id, name=tname, difficulty=difficulty, estimated_minutes=minutes)
                db.add(topic)
                db.flush()
                for text, right, wrong, why in questions:
                    q = Question(topic_id=topic.id, text=text, explanation=why)
                    q.options = [QuestionOption(text=right, is_correct=True, position=0)] + [
                        QuestionOption(text=w, is_correct=False, position=i + 1) for i, w in enumerate(wrong)]
                    db.add(q)
                    n_q += 1
        db.commit()
        print(f"Seeded {EMAIL} / {PASSWORD}: {len(DATA)} subjects, 12 topics, {n_q} questions, 3 exams.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    seed(ap.parse_args().reset)