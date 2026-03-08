package com.example.profiling.controller;

import com.example.profiling.domain.Product;
import com.example.profiling.service.ProductService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/products")
public class ProductController {

    private final ProductService productService;

    public ProductController(ProductService productService) {
        this.productService = productService;
    }

    /**
     * GET /products
     * GET /products?category=ELECTRONICS
     * GET /products?q=laptop
     * GET /products?minPrice=10&maxPrice=100
     *
     * Hammering this generates Spring MVC → Hibernate → JDBC stacks.
     */
    @GetMapping
    public List<Product> list(
            @RequestParam(required = false) String category,
            @RequestParam(required = false) String q,
            @RequestParam(required = false) BigDecimal minPrice,
            @RequestParam(required = false) BigDecimal maxPrice) {

        if (category != null) return productService.findByCategory(category);
        if (q != null)        return productService.search(q);
        if (minPrice != null && maxPrice != null)
                              return productService.findByPriceRange(minPrice, maxPrice);
        return productService.findAll();
    }

    /**
     * GET /products/report
     * Generates Spring → App (computation) stacks — com/example at the leaf.
     */
    @GetMapping("/report")
    public Map<String, Object> report() {
        return productService.computeReport();
    }

    /**
     * GET /products/csv
     * Generates Spring → App → JDK StringBuilder stacks.
     */
    @GetMapping(value = "/csv", produces = "text/csv")
    public String csv() {
        return productService.buildCsv();
    }

    /**
     * GET /products/low-stock?threshold=10
     * Additional Hibernate query path.
     */
    @GetMapping("/low-stock")
    public List<Product> lowStock(@RequestParam(defaultValue = "10") int threshold) {
        return productService.findLowStock(threshold);
    }

    @GetMapping("/{id}")
    public ResponseEntity<Product> getById(@PathVariable Long id) {
        return productService.findAll().stream()
                .filter(p -> p.getId().equals(id))
                .findFirst()
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }
}
