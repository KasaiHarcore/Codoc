"""
Values of global configuration variables.
"""

# Overall output directory for results
output_dir: str = ""

# upper bound of the number of conversation rounds for the agent
conv_round_limit: int = 15

# whether to perform layered search
enable_layered: bool = True

# timeout for test cmd execution, currently set to 5 min
test_exec_timeout: int = 300