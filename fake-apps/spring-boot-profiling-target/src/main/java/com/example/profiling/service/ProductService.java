package com.example.profiling.service;

import com.example.profiling.domain.Product;
import com.example.profiling.repository.ProductRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.*;

/**
 * Service layer — designed to generate distinct profiling layers:
 *
 *  findAll / findByCategory  →  Hibernate query path  (org/hibernate leaf)
 *  computeReport             →  in-memory computation (com/example leaf)
 *  buildCsv                  →  string building       (java/lang/StringBuilder leaf)
 *  findLowStock + save       →  Hibernate write path  (Hibernate + JDBC leaf)
 */
@Service
@Transactional(readOnly = true)
public class ProductService {

    private final ProductRepository productRepository;

    public ProductService(ProductRepository productRepository) {
        this.productRepository = productRepository;
    }

    public List<Product> findAll() {
        return productRepository.findAll();
    }

    public List<Product> findByCategory(String category) {
        return productRepository.findByCategory(category);
    }

    public List<Product> search(String query) {
        return productRepository.findByNameContainingIgnoreCase(query);
    }

    public List<Product> findByPriceRange(BigDecimal min, BigDecimal max) {
        return productRepository.findByPriceRange(min, max);
    }

    /**
     * In-memory computation — generates com/example frames at the leaf.
     * Deliberately iterates multiple times to be visible in a profile.
     */
    public Map<String, Object> computeReport() {
        List<Product> all = productRepository.findAll();

        Map<String, Long> countByCategory = new LinkedHashMap<>();
        Map<String, BigDecimal> totalPriceByCategory = new LinkedHashMap<>();
        Map<String, Integer> totalStockByCategory = new LinkedHashMap<>();

        for (Product p : all) {
            String cat = p.getCategory();
            countByCategory.merge(cat, 1L, Long::sum);
            totalPriceByCategory.merge(cat, p.getPrice(), BigDecimal::add);
            totalStockByCategory.merge(cat, p.getStock(), Integer::sum);
        }

        Map<String, Object> report = new LinkedHashMap<>();
        for (String cat : countByCategory.keySet()) {
            long count = countByCategory.get(cat);
            BigDecimal avg = totalPriceByCategory.get(cat)
                    .divide(BigDecimal.valueOf(count), 2, RoundingMode.HALF_UP);
            report.put(cat, Map.of(
                    "count", count,
                    "avgPrice", avg,
                    "totalStock", totalStockByCategory.get(cat)
            ));
        }

        // Extra pass: compute overall stats (more app-layer CPU)
        double globalAvg = all.stream()
                .mapToDouble(p -> p.getPrice().doubleValue())
                .average()
                .orElse(0.0);
        int totalStock = all.stream().mapToInt(Product::getStock).sum();

        report.put("_total", Map.of(
                "products", all.size(),
                "globalAvgPrice", BigDecimal.valueOf(globalAvg).setScale(2, RoundingMode.HALF_UP),
                "totalStock", totalStock
        ));

        return report;
    }

    /**
     * String building — generates java/lang/StringBuilder.append at the leaf.
     */
    public String buildCsv() {
        List<Product> all = productRepository.findAll();
        StringBuilder sb = new StringBuilder(all.size() * 80);
        sb.append("id,name,category,price,stock,description\n");
        for (Product p : all) {
            sb.append(p.getId()).append(',')
              .append(p.getName()).append(',')
              .append(p.getCategory()).append(',')
              .append(p.getPrice()).append(',')
              .append(p.getStock()).append(',')
              .append(p.getDescription() != null ? p.getDescription().replace(",", ";") : "")
              .append('\n');
        }
        return sb.toString();
    }

    public List<Product> findLowStock(int threshold) {
        return productRepository.findByStockLessThan(threshold);
    }

    @Transactional
    public Product save(Product product) {
        return productRepository.save(product);
    }
}
