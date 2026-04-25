-- Run: mysql -u root -p ai_travel_buddy < seed_data.sql
-- Your seven “northern / mountain” destinations. Safe re-run: upserts on id.

USE ai_travel_buddy;

INSERT INTO destinations
    (id, name, country, region, category, description, avg_cost_pkr, best_season, climate, safety_rating, rating, popularity_score, latitude, longitude, image_url, is_active)
VALUES
    (1, 'Hunza Valley', 'Pakistan', 'Gilgit-Baltistan', 'mountain', 'Alpine towns and high peaks in Gilgit-Baltistan.', 30000, 'May,Sep', '', 4.0, 4.9, 0.00, 36.3200000, 74.6500000, NULL, 1),
    (2, 'Skardu', 'Pakistan', 'Gilgit-Baltistan', 'mountain', 'Gateway to K2, cold desert, and high glacial terrain.', 28000, 'May,Sep', '', 4.0, 4.8, 0.00, 35.2871326, 75.6553123, NULL, 1),
    (3, 'Naran', 'Pakistan', 'KPK', 'mountain', 'River valley in upper Kaghan; access to Lake Saif-ul-Malook.', 20000, 'Jun,Sep', '', 4.0, 4.7, 0.00, 34.9100000, 73.6500000, NULL, 1),
    (4, 'Kaghan Valley', 'Pakistan', 'KPK', 'mountain', 'Valley along the Kunhar River, scenic road from Balakot to Naran.', 20000, 'Jun,Sep', '', 4.0, 4.7, 0.00, 34.5416700, 73.3500000, NULL, 1),
    (5, 'Fairy Meadows', 'Pakistan', 'GB', 'adventure', 'High-altitude meadow with Nanga Parbat views.', 35000, 'Jun,Sep', '', 4.0, 4.9, 0.00, 35.3872034, 74.5789292, NULL, 1),
    (6, 'Deosai Plains', 'Pakistan', 'GB', 'nature', 'High plateaus, wildlife, and open landscapes.', 32000, 'Jul,Sep', '', 4.0, 4.8, 0.00, 35.0137600, 75.4742200, NULL, 1),
    (7, 'Shogran', 'Pakistan', 'KPK', 'hill', 'Pine forest, viewpoints, and base for Siri Paye / Makra.', 18000, 'May,Sep', '', 4.0, 4.6, 0.00, 34.6409377, 73.4639560, NULL, 1)
ON DUPLICATE KEY UPDATE
    name = VALUES(name),
    country = VALUES(country),
    region = VALUES(region),
    category = VALUES(category),
    description = VALUES(description),
    avg_cost_pkr = VALUES(avg_cost_pkr),
    best_season = VALUES(best_season),
    climate = VALUES(climate),
    safety_rating = VALUES(safety_rating),
    rating = VALUES(rating),
    popularity_score = VALUES(popularity_score),
    latitude = VALUES(latitude),
    longitude = VALUES(longitude),
    image_url = VALUES(image_url),
    is_active = VALUES(is_active);
