package com.example.profiling;

import com.example.profiling.domain.Product;
import com.example.profiling.service.ProductService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.util.Random;

/**
 * Inserts 500 products at startup across 5 categories.
 * Enough volume that Hibernate queries produce visible stack depth during profiling.
 */
@Component
public class DataLoader implements CommandLineRunner {

    private static final Logger log = LoggerFactory.getLogger(DataLoader.class);

    private static final String[] CATEGORIES = {
        "ELECTRONICS", "CLOTHING", "FOOD", "BOOKS", "SPORTS"
    };

    private static final String[][] NAMES_BY_CATEGORY = {
        // ELECTRONICS
        { "Laptop Pro", "Wireless Headphones", "USB-C Hub", "Mechanical Keyboard", "4K Monitor",
          "Webcam HD", "External SSD", "Smart Speaker", "Graphics Card", "Gaming Mouse" },
        // CLOTHING
        { "Denim Jacket", "Running Shoes", "Wool Sweater", "Cargo Pants", "Leather Belt",
          "Baseball Cap", "Waterproof Jacket", "Cotton T-Shirt", "Hiking Boots", "Fleece Vest" },
        // FOOD
        { "Organic Coffee", "Dark Chocolate", "Granola Mix", "Olive Oil", "Jasmine Tea",
          "Almond Butter", "Protein Bar", "Sparkling Water", "Trail Mix", "Hot Sauce" },
        // BOOKS
        { "Clean Code", "Design Patterns", "The Pragmatic Programmer", "Refactoring",
          "Domain-Driven Design", "Working Effectively with Legacy Code", "Release It",
          "Site Reliability Engineering", "The Phoenix Project", "Accelerate" },
        // SPORTS
        { "Yoga Mat", "Resistance Bands", "Jump Rope", "Foam Roller", "Pull-Up Bar",
          "Kettlebell 16kg", "Running Belt", "Water Bottle", "Gym Gloves", "Ankle Weights" }
    };

    private final ProductService productService;

    public DataLoader(ProductService productService) {
        this.productService = productService;
    }

    @Override
    public void run(String... args) {
        Random rng = new Random(42);
        int count = 0;

        for (int categoryIndex = 0; categoryIndex < CATEGORIES.length; categoryIndex++) {
            String category = CATEGORIES[categoryIndex];
            String[] names = NAMES_BY_CATEGORY[categoryIndex];

            // 100 products per category — 10 base names × 10 variants
            for (int variant = 1; variant <= 10; variant++) {
                for (String baseName : names) {
                    String name = baseName + (variant > 1 ? " v" + variant : "");
                    BigDecimal price = BigDecimal.valueOf(5 + rng.nextInt(995) + rng.nextDouble())
                            .setScale(2, java.math.RoundingMode.HALF_UP);
                    int stock = rng.nextInt(200);
                    String description = "A quality " + category.toLowerCase() + " product: " + name
                            + ". Variant " + variant + ". SKU-" + (count + 1000);
                    productService.save(new Product(name, category, price, stock, description));
                    count++;
                }
            }
        }

        log.info("DataLoader: {} products inserted across {} categories", count, CATEGORIES.length);
        log.info("Ready — http://localhost:8080/products");
    }
}
