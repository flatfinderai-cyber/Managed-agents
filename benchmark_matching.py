import timeit

setup_code = """
import random

def generate_matches(n):
    return [
        {
            "id": f"id_{i}",
            "listing_id": f"list_{i}",
            "status": "pending",
            "confirmed_tenant_at": None,
            "confirmed_landlord_at": None,
            "created_at": "2023-01-01T00:00:00Z"
        }
        for i in range(n)
    ]

matches = generate_matches(1000)
"""

test_for_loop = """
landlord_safe = []
for m in matches:
    landlord_safe.append({
        "match_id": m.get("id"),
        "listing_id": m.get("listing_id"),
        "status": m.get("status"),
        "confirmed_tenant_at": m.get("confirmed_tenant_at"),
        "confirmed_landlord_at": m.get("confirmed_landlord_at"),
        "created_at": m.get("created_at"),
        "message": "A verified tenant has been matched to your listing.",
    })
"""

test_list_comp = """
landlord_safe = [{
    "match_id": m.get("id"),
    "listing_id": m.get("listing_id"),
    "status": m.get("status"),
    "confirmed_tenant_at": m.get("confirmed_tenant_at"),
    "confirmed_landlord_at": m.get("confirmed_landlord_at"),
    "created_at": m.get("created_at"),
    "message": "A verified tenant has been matched to your listing.",
} for m in matches]
"""

# Run benchmarks
n_iterations = 10000

time_for = timeit.timeit(stmt=test_for_loop, setup=setup_code, number=n_iterations)
time_comp = timeit.timeit(stmt=test_list_comp, setup=setup_code, number=n_iterations)

print(f"Iterations: {n_iterations}")
print(f"For loop + append: {time_for:.4f} seconds")
print(f"List comprehension: {time_comp:.4f} seconds")

improvement = (time_for - time_comp) / time_for * 100
print(f"Performance improvement: {improvement:.2f}%")
