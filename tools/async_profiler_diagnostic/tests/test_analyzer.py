# tests/test_analyzer.py

from async_profiler_diagnostic.analyzer import classify_frame, analyze
from async_profiler_diagnostic.parser import parse_collapsed, ProfileData

APP_PREFIX = "com/example/myapp"


# --- classify_frame ---

def test_classify_app_slash_notation():
    assert classify_frame("com/example/myapp/service/UserService.findById", APP_PREFIX) == "App"


def test_classify_app_dot_notation():
    # dot notation is normalised internally
    assert classify_frame("com.example.myapp.service.UserService.findById", APP_PREFIX) == "App"


def test_classify_app_prefix_dot_notation():
    # prefix itself in dot notation
    assert classify_frame("com/example/myapp/batch/Job.run", "com.example.myapp") == "App"


def test_classify_spring():
    assert classify_frame("org/springframework/web/servlet/DispatcherServlet.doDispatch", "") == "Spring"


def test_classify_hibernate():
    assert classify_frame("org/hibernate/query/internal/AbstractProducedQuery.list", "") == "Hibernate"


def test_classify_jakarta_persistence():
    assert classify_frame("jakarta/persistence/EntityManager.find", "") == "Hibernate"


def test_classify_jdbc_java_sql():
    assert classify_frame("java/sql/PreparedStatement.executeQuery", "") == "JDBC"


def test_classify_jdbc_mysql():
    assert classify_frame("com/mysql/cj/NativeSession.execSQL", "") == "JDBC"


def test_classify_jdbc_postgresql():
    assert classify_frame("org/postgresql/jdbc/PgPreparedStatement.execute", "") == "JDBC"


def test_classify_jdbc_h2():
    assert classify_frame("org/h2/jdbc/JdbcPreparedStatement.executeQuery", "") == "JDBC"


def test_classify_jdbc_h2_engine():
    assert classify_frame("org/h2/engine/Session.query", "") == "JDBC"


def test_classify_jdk_java():
    assert classify_frame("java/lang/StringBuilder.append", "") == "JDK"


def test_classify_jdk_module():
    assert classify_frame("jdk/internal/misc/Unsafe.park", "") == "JDK"


def test_classify_jdk_sun():
    assert classify_frame("sun/nio/ch/SocketDispatcher.read0", "") == "JDK"


def test_classify_native_no_slash():
    assert classify_frame("__psynch_cvwait", "") == "JVM/Native"


def test_classify_native_cpp_style():
    assert classify_frame("WatcherThread::run", "") == "JVM/Native"


def test_classify_native_underscore():
    assert classify_frame("_pthread_start", "") == "JVM/Native"


def test_classify_other_unknown_package():
    assert classify_frame("com/other/unknown/Library.method", "") == "Other"


def test_classify_no_app_prefix_app_frame_falls_to_other():
    # without app_prefix, app frames fall through to Other
    assert classify_frame("com/example/myapp/Service.doWork", "") == "Other"


# --- analyze ---

def test_analyze_empty_profile():
    result = analyze(ProfileData(), app_prefix=APP_PREFIX, top_n=10)
    assert result["total_samples"] == 0
    assert result["layer_distribution"] == []
    assert result["hot_stacks"] == []


def test_analyze_total_samples(sample_collapsed):
    profile = parse_collapsed(sample_collapsed)
    result = analyze(profile, app_prefix=APP_PREFIX, top_n=10)
    assert result["total_samples"] == 147


def test_analyze_layer_distribution_app(sample_collapsed):
    profile = parse_collapsed(sample_collapsed)
    result = analyze(profile, app_prefix=APP_PREFIX, top_n=10)
    layers = {e["layer"]: e["samples"] for e in result["layer_distribution"]}
    # App: stacks with leaf in com/example/myapp (Order.isEligible=30, Statistics.mean=20)
    assert layers.get("App", 0) == 50


def test_analyze_layer_distribution_jdbc(sample_collapsed):
    profile = parse_collapsed(sample_collapsed)
    result = analyze(profile, app_prefix=APP_PREFIX, top_n=10)
    layers = {e["layer"]: e["samples"] for e in result["layer_distribution"]}
    assert layers.get("JDBC", 0) == 40


def test_analyze_layer_distribution_jdk(sample_collapsed):
    profile = parse_collapsed(sample_collapsed)
    result = analyze(profile, app_prefix=APP_PREFIX, top_n=10)
    layers = {e["layer"]: e["samples"] for e in result["layer_distribution"]}
    assert layers.get("JDK", 0) == 25


def test_analyze_layer_distribution_hibernate(sample_collapsed):
    profile = parse_collapsed(sample_collapsed)
    result = analyze(profile, app_prefix=APP_PREFIX, top_n=10)
    layers = {e["layer"]: e["samples"] for e in result["layer_distribution"]}
    assert layers.get("Hibernate", 0) == 15


def test_analyze_layer_distribution_sorted_descending(sample_collapsed):
    profile = parse_collapsed(sample_collapsed)
    result = analyze(profile, app_prefix=APP_PREFIX, top_n=10)
    counts = [e["samples"] for e in result["layer_distribution"]]
    assert counts == sorted(counts, reverse=True)


def test_analyze_pct_sums_to_100(sample_collapsed):
    profile = parse_collapsed(sample_collapsed)
    result = analyze(profile, app_prefix=APP_PREFIX, top_n=10)
    total_pct = sum(e["pct"] for e in result["layer_distribution"])
    assert abs(total_pct - 100.0) < 1.0  # allow rounding


def test_analyze_hot_stacks_sorted(sample_collapsed):
    profile = parse_collapsed(sample_collapsed)
    result = analyze(profile, app_prefix=APP_PREFIX, top_n=10)
    counts = [s["count"] for s in result["hot_stacks"]]
    assert counts == sorted(counts, reverse=True)


def test_analyze_top_n_limit(sample_collapsed):
    profile = parse_collapsed(sample_collapsed)
    result = analyze(profile, app_prefix=APP_PREFIX, top_n=3)
    assert len(result["hot_stacks"]) == 3


def test_analyze_hot_stack_rank(sample_collapsed):
    profile = parse_collapsed(sample_collapsed)
    result = analyze(profile, app_prefix=APP_PREFIX, top_n=10)
    ranks = [s["rank"] for s in result["hot_stacks"]]
    assert ranks == list(range(1, len(ranks) + 1))


def test_analyze_hot_stack_leaf_classified(sample_collapsed):
    profile = parse_collapsed(sample_collapsed)
    result = analyze(profile, app_prefix=APP_PREFIX, top_n=1)
    top = result["hot_stacks"][0]
    # top stack has 40 samples, leaf is com/mysql/cj/NativeSession.execSQL -> JDBC
    assert top["count"] == 40
    assert top["layer"] == "JDBC"
    assert top["leaf"] == "com/mysql/cj/NativeSession.execSQL"
