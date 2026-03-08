#!/usr/bin/env bash
# load.sh — Generate sustained load for async-profiler capture.
#
# Usage:
#   ./load.sh                  # loops until Ctrl+C
#
# In another terminal, while this is running:
#   asprof -d 30 -e cpu -o collapsed -f cpu.collapsed $(jps | grep ProfilingApp | cut -d' ' -f1)
#
# Then analyze:
#   python ../../tools/async_profiler_diagnostic/get-async-profiler-diagnostic.py \
#          cpu.collapsed --app-prefix com/example/profiling

BASE="http://localhost:8080"

echo "Load generator started — hit Ctrl+C to stop"
echo "In another terminal run:"
echo "  asprof -d 30 -e cpu -o collapsed -f cpu.collapsed \$(jps | grep ProfilingApp | cut -d' ' -f1)"
echo ""

i=0
while true; do
    # Rotate through endpoints to hit all layers
    case $((i % 6)) in
        0) curl -s "$BASE/products" > /dev/null ;;                          # Hibernate findAll
        1) curl -s "$BASE/products?category=ELECTRONICS" > /dev/null ;;     # Hibernate filtered
        2) curl -s "$BASE/products/report" > /dev/null ;;                   # App computation
        3) curl -s "$BASE/products/csv" > /dev/null ;;                      # StringBuilder
        4) curl -s "$BASE/products?minPrice=10&maxPrice=100" > /dev/null ;; # JPQL range query
        5) curl -s "$BASE/products/low-stock?threshold=20" > /dev/null ;;   # Hibernate low-stock
    esac
    i=$((i + 1))
done
