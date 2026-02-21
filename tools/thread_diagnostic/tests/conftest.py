# tools/thread_diagnostic/tests/conftest.py
import pytest


@pytest.fixture
def simple_thread_dump():
    """Minimal healthy thread dump - pool with mixed states (not saturated)."""
    return '''2024-01-15 10:30:45
Full thread dump OpenJDK 64-Bit Server VM (17.0.1+12 mixed mode):

"main" #1 prio=5 os_prio=0 tid=0x00007f1234567890 nid=0x1 runnable
   java.lang.Thread.State: RUNNABLE
	at com.example.Main.main(Main.java:10)

"GC Thread#0" #2 daemon prio=5 os_prio=0 tid=0x00007f1234567891 nid=0x2 runnable

"http-nio-8080-exec-1" #10 daemon prio=5 os_prio=0 tid=0x00007f1234567892 nid=0xa runnable
   java.lang.Thread.State: RUNNABLE
	at com.example.Controller.handle(Controller.java:50)

"http-nio-8080-exec-2" #11 daemon prio=5 os_prio=0 tid=0x00007f1234567893 nid=0xb runnable
   java.lang.Thread.State: RUNNABLE
	at com.example.Controller.handle(Controller.java:50)

"http-nio-8080-exec-3" #12 daemon prio=5 os_prio=0 tid=0x00007f1234567894 nid=0xc waiting on condition
   java.lang.Thread.State: WAITING (parking)
	at sun.misc.Unsafe.park(Native Method)

"http-nio-8080-exec-4" #13 daemon prio=5 os_prio=0 tid=0x00007f1234567895 nid=0xd runnable
   java.lang.Thread.State: RUNNABLE
	at com.example.Controller.process(Controller.java:80)
'''


@pytest.fixture
def deadlock_thread_dump():
    """Thread dump with deadlock."""
    return '''2024-01-15 10:30:45
Full thread dump OpenJDK 64-Bit Server VM (17.0.1+12 mixed mode):

"Thread-1" #10 prio=5 os_prio=0 tid=0x00007f1234567890 nid=0x1 waiting for monitor entry
   java.lang.Thread.State: BLOCKED (on object monitor)
	at com.example.DeadlockDemo.methodA(DeadlockDemo.java:20)
	- waiting to lock <0x00000000e1234567> (a java.lang.Object)
	- locked <0x00000000e7654321> (a java.lang.Object)

"Thread-2" #11 prio=5 os_prio=0 tid=0x00007f1234567891 nid=0x2 waiting for monitor entry
   java.lang.Thread.State: BLOCKED (on object monitor)
	at com.example.DeadlockDemo.methodB(DeadlockDemo.java:30)
	- waiting to lock <0x00000000e7654321> (a java.lang.Object)
	- locked <0x00000000e1234567> (a java.lang.Object)

Found 1 deadlock.
'''


@pytest.fixture
def contention_thread_dump():
    """Thread dump with lock contention - multiple threads blocked on same lock."""
    return '''2024-01-15 10:30:45
Full thread dump OpenJDK 64-Bit Server VM (17.0.1+12 mixed mode):

"worker-1" #10 prio=5 os_prio=0 tid=0x00007f1234567890 nid=0xa runnable
   java.lang.Thread.State: RUNNABLE
	at com.example.Service.process(Service.java:50)
	- locked <0x00000000e1234567> (a java.lang.Object)

"worker-2" #11 prio=5 os_prio=0 tid=0x00007f1234567891 nid=0xb waiting for monitor entry
   java.lang.Thread.State: BLOCKED (on object monitor)
	at com.example.Service.process(Service.java:50)
	- waiting to lock <0x00000000e1234567> (a java.lang.Object)

"worker-3" #12 prio=5 os_prio=0 tid=0x00007f1234567892 nid=0xc waiting for monitor entry
   java.lang.Thread.State: BLOCKED (on object monitor)
	at com.example.Service.process(Service.java:50)
	- waiting to lock <0x00000000e1234567> (a java.lang.Object)

"worker-4" #13 prio=5 os_prio=0 tid=0x00007f1234567893 nid=0xd waiting for monitor entry
   java.lang.Thread.State: BLOCKED (on object monitor)
	at com.example.Service.process(Service.java:50)
	- waiting to lock <0x00000000e1234567> (a java.lang.Object)
'''
