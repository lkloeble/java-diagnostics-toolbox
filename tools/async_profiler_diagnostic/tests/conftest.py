# tools/async_profiler_diagnostic/tests/conftest.py
import pytest


@pytest.fixture
def minimal_collapsed():
    """Three real lines from Laurent's gc/harness app (asprof 4.3, macOS)."""
    return (
        "thread_start;_pthread_start;thread_native_entry;Thread::call_run;"
        "WatcherThread::run;WatcherThread::sleep;Monitor::wait_without_safepoint_check;"
        "PlatformMonitor::wait;__psynch_cvwait 2\n"
        "gc/harness/MemoryBehaviorApp.main 1\n"
        "gc/harness/MemoryBehaviorApp.main;gc/harness/MemoryBehaviorApp.retainUpTo;"
        "gc/harness/MemoryBehaviorApp.retainedBytes 1\n"
    )


@pytest.fixture
def sample_collapsed():
    """Synthetic sample covering all layers (App, Spring, Hibernate, JDBC, JDK, JVM/Native, Other)."""
    return """\
# async-profiler CPU sample — Spring Boot + Hibernate
thread_start;_pthread_start;thread_native_entry;Thread::call_run;JavaThread::thread_main_inner;java/lang/Thread.run;org/springframework/web/servlet/DispatcherServlet.doDispatch;com/example/myapp/controller/UserController.getUser;com/example/myapp/service/UserService.findById;org/hibernate/query/internal/AbstractProducedQuery.list;com/mysql/cj/jdbc/ClientPreparedStatement.executeQuery;com/mysql/cj/NativeSession.execSQL 40
thread_start;_pthread_start;thread_native_entry;Thread::call_run;JavaThread::thread_main_inner;java/lang/Thread.run;org/springframework/web/servlet/DispatcherServlet.doDispatch;com/example/myapp/controller/OrderController.listOrders;com/example/myapp/service/OrderService.filterByStatus;com/example/myapp/domain/Order.isEligible 30
thread_start;_pthread_start;thread_native_entry;Thread::call_run;JavaThread::thread_main_inner;java/lang/Thread.run;com/example/myapp/controller/ReportController.exportCsv;com/example/myapp/service/ReportService.buildCsv;java/lang/StringBuilder.append 25
com/example/myapp/batch/ReportGenerator.computeMetrics;com/example/myapp/util/Statistics.mean 20
thread_start;_pthread_start;thread_native_entry;Thread::call_run;JavaThread::thread_main_inner;java/lang/Thread.run;org/springframework/aop/framework/ReflectiveMethodInvocation.proceed;org/springframework/transaction/interceptor/TransactionInterceptor.invoke;com/example/myapp/service/PaymentService.processPayment;org/hibernate/loader/Loader.loadEntityBatch;org/hibernate/event/internal/DefaultLoadEventListener.proxyOrLoad 15
thread_start;_pthread_start;thread_native_entry;Thread::call_run;VMThread::run;VM_GenCollectFull::doit 8
thread_start;_pthread_start;thread_native_entry;Thread::call_run;JavaThread::thread_main_inner;java/lang/Thread.run;com/example/myapp/controller/UserController.createUser;org/springframework/aop/framework/ReflectiveMethodInvocation.proceed;org/springframework/validation/beanvalidation/MethodValidationInterceptor.invoke 5
thread_start;_pthread_start;thread_native_entry;Thread::call_run;WatcherThread::run;WatcherThread::sleep;Monitor::wait_without_safepoint_check;PlatformMonitor::wait;__psynch_cvwait 2
gc/harness/MemoryBehaviorApp.main 1
gc/harness/MemoryBehaviorApp.main;gc/harness/MemoryBehaviorApp.retainUpTo;gc/harness/MemoryBehaviorApp.retainedBytes 1
"""
