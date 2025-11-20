from LimerickAgent import try_parse_json_from_texts, normalize_research_dict, infer_years_from_text


def run_tests():
    print('Test 1: explicit years array')
    research_obj = {
        'years': [
            {'year': 2024, 'share_price': '£12.34', 'pe_ratio': 15.2, 'dividends': '0.45', 'market_cap': '£1.2B'},
            {'year': 2023, 'share_price': '£10.20', 'pe_ratio': 18.1, 'dividends': '0.40', 'market_cap': '£1.1B'},
            {'year': 2022, 'share_price': '£9.50', 'pe_ratio': 20.3, 'dividends': '0.38', 'market_cap': '£1.0B'}
        ]
    }
    normalized = normalize_research_dict(research_obj, [])
    print('Normalized:', normalized)
    assert len(normalized) == 3 and normalized[0]['year'] == 2024

    print('Test 2: year keys at top level')
    research_obj = {
        '2024': {'share_price': '$50', 'pe_ratio': 10},
        '2023': {'share_price': '$45', 'pe_ratio': 12},
        '2022': {'share_price': '$40', 'pe_ratio': 15}
    }
    normalized = normalize_research_dict(research_obj, [])
    print('Normalized:', normalized)
    assert len(normalized) == 3 and normalized[0]['year'] == 2024

    print('Test 3: metric maps')
    research_obj = {
        'share_price': {'2024': '$60', '2023': '$55'},
        'pe_ratio': {'2024': 11}
    }
    normalized = normalize_research_dict(research_obj, [])
    print('Normalized:', normalized)
    assert len(normalized) == 3

    print('Test 4: flattened single-year')
    research_obj = {'year': 2024, 'share_price': '€20', 'pe_ratio': 9}
    normalized = normalize_research_dict(research_obj, [])
    print('Normalized:', normalized)
    assert len(normalized) == 3 and normalized[0]['year'] == 2024

    print('Test 5: infer years from text parts')
    texts = ['In 2022 the share price was $10.00 and market cap $1B.', 'By 2023 it rose to $12.50. In 2021 it was $8.00.']
    inferred = infer_years_from_text(texts)
    print('Inferred:', inferred)
    normalized = normalize_research_dict({}, texts)
    print('Normalized from empty obj using inference:', normalized)
    assert len(normalized) == 3

    print('All tests passed')


if __name__ == '__main__':
    run_tests()

