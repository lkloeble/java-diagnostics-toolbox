package com.example.profiling.domain;

import jakarta.persistence.*;
import java.math.BigDecimal;

@Entity
@Table(name = "products")
public class Product {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String name;

    @Column(nullable = false)
    private String category;

    @Column(nullable = false, precision = 10, scale = 2)
    private BigDecimal price;

    @Column(nullable = false)
    private int stock;

    @Column(length = 500)
    private String description;

    public Product() {}

    public Product(String name, String category, BigDecimal price, int stock, String description) {
        this.name = name;
        this.category = category;
        this.price = price;
        this.stock = stock;
        this.description = description;
    }

    public Long getId()              { return id; }
    public String getName()          { return name; }
    public String getCategory()      { return category; }
    public BigDecimal getPrice()     { return price; }
    public int getStock()            { return stock; }
    public String getDescription()   { return description; }
}
