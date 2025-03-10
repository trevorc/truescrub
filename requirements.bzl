def requirement(name):
    """Return the name of a pip dependency from the pip repository.
    
    Args:
        name: The PyPI package name.
    
    Returns:
        The label of the pip dependency in Bazel.
    """
    # Preserve the exact case of the package name, as import statements are case-sensitive
    return "@pip_deps//{}:{}".format(name, name)