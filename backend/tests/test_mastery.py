from app.services.mastery import calculate_status


def test_mastery_calculation():
    assert calculate_status(0, 0, 0, 0, None)[0] == "new"
    assert calculate_status(1, 0, 1, 0, "wrong")[0] == "weak"
    assert calculate_status(3, 3, 0, 3, "correct")[0] == "learning"
    assert calculate_status(5, 5, 0, 5, "correct")[0] == "mastered"
