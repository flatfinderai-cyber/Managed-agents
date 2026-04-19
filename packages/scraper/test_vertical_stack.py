from vertical_stack import ListingCandidate, evaluate_listing


def test_pass_clean_listing():
    listing = ListingCandidate(
        external_id="abc-1",
        source="kijiji",
        title="2 bed apartment near transit",
        city="Toronto",
        url="https://example.com/listing/1",
        price_local=2400,
        bedrooms=2,
        description="Verified unit with clear terms and in-person viewing available.",
    )

    result = evaluate_listing(listing, market_median_price=2500)
    assert result.decision == "pass"
    assert result.layer_results["layer1_listing_integrity"]["status"] == "pass"


def test_quarantine_for_price_anomaly():
    listing = ListingCandidate(
        external_id="abc-2",
        source="kijiji",
        title="Cheap unit",
        city="Toronto",
        url="https://example.com/listing/2",
        price_local=900,
        bedrooms=1,
        description="Good apartment.",
    )

    result = evaluate_listing(listing, market_median_price=2500)
    assert result.decision == "quarantine"
    assert result.layer_results["layer1_listing_integrity"]["status"] == "quarantine"


def test_block_for_payment_before_viewing_phrase():
    listing = ListingCandidate(
        external_id="abc-3",
        source="craigslist",
        title="Send deposit before viewing",
        city="Toronto",
        url="https://example.com/listing/3",
        price_local=2200,
        bedrooms=2,
        description="Please pay before viewing to hold unit.",
    )

    result = evaluate_listing(listing, market_median_price=2200)
    assert result.decision == "block"
    assert result.layer_results["layer2_language_analysis"]["status"] == "block"
