package com.example.profiling;

import com.example.profiling.service.ProductService;
import jakarta.annotation.PreDestroy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Background load generator — starts automatically after application startup.
 * Keeps all service paths hot so async-profiler captures meaningful stacks at any time.
 *
 * 4 threads, each hammering a different code path:
 *   Thread 0 — findAll + findByCategory      → Hibernate query stacks
 *   Thread 1 — computeReport                 → App computation stacks (com/example leaf)
 *   Thread 2 — buildCsv                      → JDK StringBuilder stacks
 *   Thread 3 — findByPriceRange + findLowStock → JPQL + Hibernate write path
 */
@Component
public class LoadGenerator {

    private static final Logger log = LoggerFactory.getLogger(LoadGenerator.class);

    private final ProductService productService;
    private final ExecutorService executor = Executors.newFixedThreadPool(4, r -> {
        Thread t = new Thread(r, "load-gen-" + System.nanoTime());
        t.setDaemon(true);
        return t;
    });

    public LoadGenerator(ProductService productService) {
        this.productService = productService;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void start() {
        log.info("LoadGenerator: starting 4 background workers");

        executor.submit(this::runHibernateQueries);
        executor.submit(this::runAppComputation);
        executor.submit(this::runStringBuilding);
        executor.submit(this::runJpqlQueries);
    }

    /** Thread 0 — Hibernate findAll / findByCategory */
    private void runHibernateQueries() {
        String[] categories = {"ELECTRONICS", "CLOTHING", "FOOD", "BOOKS", "SPORTS"};
        int i = 0;
        while (!Thread.currentThread().isInterrupted()) {
            try {
                productService.findAll();
                productService.findByCategory(categories[i % categories.length]);
                i++;
            } catch (Exception e) {
                if (Thread.currentThread().isInterrupted()) break;
            }
        }
    }

    /** Thread 1 — App in-memory computation (com/example frames at leaf) */
    private void runAppComputation() {
        while (!Thread.currentThread().isInterrupted()) {
            try {
                productService.computeReport();
            } catch (Exception e) {
                if (Thread.currentThread().isInterrupted()) break;
            }
        }
    }

    /** Thread 2 — StringBuilder / JDK string path */
    private void runStringBuilding() {
        while (!Thread.currentThread().isInterrupted()) {
            try {
                productService.buildCsv();
            } catch (Exception e) {
                if (Thread.currentThread().isInterrupted()) break;
            }
        }
    }

    /** Thread 3 — JPQL range query + low-stock Hibernate path */
    private void runJpqlQueries() {
        while (!Thread.currentThread().isInterrupted()) {
            try {
                productService.findByPriceRange(BigDecimal.valueOf(10), BigDecimal.valueOf(200));
                productService.findLowStock(20);
                productService.search("pro");
            } catch (Exception e) {
                if (Thread.currentThread().isInterrupted()) break;
            }
        }
    }

    @PreDestroy
    public void stop() {
        log.info("LoadGenerator: shutting down");
        executor.shutdownNow();
    }
}
