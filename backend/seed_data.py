from models import Problem

PROBLEMS = [
    Problem(
        id="parking-lot",
        title="Parking Lot System",
        difficulty="Medium",
        summary="Design a multi-level parking lot that supports multiple vehicle types, "
                "spot allocation, and fee calculation.",
        requirements=[
            "Support multiple vehicle types (motorcycle, car, bus) with different spot sizes.",
            "Allocate the nearest/most appropriate free spot to an entering vehicle.",
            "Track occupancy per level and raise/handle a 'lot full' scenario.",
            "Calculate a parking fee on exit based on duration and vehicle type.",
            "Support adding a new payment method later without rewriting the ticketing logic.",
        ],
        core_entities=["ParkingLot", "ParkingSpot", "Vehicle", "Ticket", "Level", "PaymentStrategy"],
        rubric=[
            "Vehicle types modeled via inheritance/interface, not a type-string with if/else.",
            "Spot allocation logic isolated behind its own abstraction (e.g. a strategy), not hardcoded in ParkingLot.",
            "Ticket lifecycle (issued -> paid -> closed) is explicit.",
            "Fee calculation is pluggable/strategy-based so new pricing rules don't require touching core flow.",
            "Handles the 'lot full' and 'spot already taken' edge cases explicitly.",
        ],
        tags=["classic", "strategy-pattern"],
    ),
    Problem(
        id="elevator-system",
        title="Elevator System",
        difficulty="Hard",
        summary="Design the control system for a bank of elevators in a building, handling "
                "request scheduling and direction changes.",
        requirements=[
            "Handle external hall requests (up/down from a floor) and internal cabin requests.",
            "Decide which elevator serves a given request when multiple elevators exist.",
            "Model direction state (idle, moving up, moving down) and door state.",
            "Support at least one scheduling strategy (e.g. nearest-car or SCAN/look) and allow swapping it.",
            "Handle a request arriving while the elevator is already mid-route.",
        ],
        core_entities=["Elevator", "ElevatorController", "Request", "SchedulingStrategy", "Door", "Floor"],
        rubric=[
            "Clear separation between an individual Elevator (state) and a Controller (dispatch decisions).",
            "Scheduling algorithm is behind an interface so nearest-car vs SCAN can be swapped.",
            "Direction/door state modeled explicitly (state pattern or explicit enum + transition rules), not ad hoc booleans.",
            "Concurrent/mid-route requests are addressed, not ignored.",
            "Multiple elevators and how the controller picks among them is addressed.",
        ],
        tags=["classic", "state-pattern", "scheduling"],
    ),
    Problem(
        id="vending-machine",
        title="Vending Machine",
        difficulty="Easy",
        summary="Design a vending machine that accepts money, dispenses items, and gives change, "
                "modeled with explicit states.",
        requirements=[
            "Support selecting an item, inserting money, dispensing the item, and returning change.",
            "Handle insufficient funds and out-of-stock items.",
            "Model the machine's states explicitly (idle, has money, dispensing, out of stock, etc.).",
            "Support restocking / inventory management.",
            "Make it straightforward to add a new item type or a new payment method (card) later.",
        ],
        core_entities=["VendingMachine", "Inventory", "Item", "Coin", "MachineState", "Transaction"],
        rubric=[
            "State pattern (or equivalent explicit state machine) used instead of nested if/else on flags.",
            "Inventory management is a separate responsibility from the state machine.",
            "Insufficient-funds and out-of-stock are explicit, testable states/branches.",
            "Change calculation is isolated and correct for edge amounts.",
            "Design leaves an obvious seam for a new payment method.",
        ],
        tags=["classic", "state-pattern", "beginner-friendly"],
    ),
]
