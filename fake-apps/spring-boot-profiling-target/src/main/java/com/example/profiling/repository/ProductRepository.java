package com.example.profiling.repository;

import com.example.profiling.domain.Product;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.math.BigDecimal;
import java.util.List;

public interface ProductRepository extends JpaRepository<Product, Long> {

    List<Product> findByCategory(String category);

    List<Product> findByNameContainingIgnoreCase(String name);

    List<Product> findByStockLessThan(int threshold);

    // Named JPQL query — goes through Hibernate query engine
    @Query("SELECT p FROM Product p WHERE p.price BETWEEN :min AND :max ORDER BY p.price DESC")
    List<Product> findByPriceRange(BigDecimal min, BigDecimal max);
}
