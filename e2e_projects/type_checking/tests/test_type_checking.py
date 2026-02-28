from type_checking import hello, a_hello_wrapper, mutate_me

def test_hello():
    assert hello() == "Hello from type-checking!"

def test_a_hello_wrapper():
    assert isinstance(a_hello_wrapper(), str)

def test_mutate_me():
    assert mutate_me() == "charlie"
