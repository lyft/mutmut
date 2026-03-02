"""Tests for mutmut.utils.format_utils module."""

import pytest

from mutmut.utils.format_utils import CLASS_NAME_SEPARATOR
from mutmut.utils.format_utils import get_module_from_key
from mutmut.utils.format_utils import mangle_function_name
from mutmut.utils.format_utils import mangled_name_from_mutant_name
from mutmut.utils.format_utils import parse_mutant_key
from mutmut.utils.format_utils import raw_func_name_from_mangled


class TestMangledNameFromMutantName:
    """Tests for mangled_name_from_mutant_name function."""

    def test_extracts_mangled_name(self):
        """Test extracting mangled name from mutant name."""
        result = mangled_name_from_mutant_name("module.x_foo__mutmut_1")
        assert result == "module.x_foo"

    def test_handles_higher_mutant_numbers(self):
        """Test with higher mutant numbers."""
        result = mangled_name_from_mutant_name("module.x_foo__mutmut_999")
        assert result == "module.x_foo"

    def test_handles_class_methods(self):
        """Test with class method format."""
        result = mangled_name_from_mutant_name(
            f"module.x{CLASS_NAME_SEPARATOR}Class{CLASS_NAME_SEPARATOR}method__mutmut_1"
        )
        assert result == f"module.x{CLASS_NAME_SEPARATOR}Class{CLASS_NAME_SEPARATOR}method"

    def test_raises_on_invalid_format(self):
        """Test that invalid format raises AssertionError."""
        with pytest.raises(AssertionError):
            mangled_name_from_mutant_name("module.foo")


class TestMangleFunctionName:
    """Tests for mangle_function_name function."""

    def test_top_level_function(self):
        """Test mangling a top-level function."""
        result = mangle_function_name(name="foo", class_name=None)
        assert result == "x_foo"

    def test_class_method(self):
        """Test mangling a class method."""
        result = mangle_function_name(name="method", class_name="MyClass")
        assert result == f"x{CLASS_NAME_SEPARATOR}MyClass{CLASS_NAME_SEPARATOR}method"


class TestParseMutantKey:
    """Tests for parse_mutant_key function."""

    def test_parses_top_level_function(self):
        """Test parsing a top-level function key."""
        func_name, class_name = parse_mutant_key("x_foo")
        assert func_name == "foo"
        assert class_name is None

    def test_parses_class_method(self):
        """Test parsing a class method key."""
        key = f"x{CLASS_NAME_SEPARATOR}MyClass{CLASS_NAME_SEPARATOR}method"
        func_name, class_name = parse_mutant_key(key)
        assert func_name == "method"
        assert class_name == "MyClass"

    def test_raises_on_invalid_format(self):
        """Test that invalid format raises AssertionError."""
        with pytest.raises(AssertionError):
            parse_mutant_key("foo")  # Missing x_ prefix


class TestGetModuleFromKey:
    """Tests for get_module_from_key function."""

    def test_simple_module(self):
        """Test extracting module from simple key."""
        result = get_module_from_key("app.x_foo")
        assert result == "app"

    def test_nested_module(self):
        """Test extracting module from nested key."""
        result = get_module_from_key("app.utils.x_helper")
        assert result == "app.utils"

    def test_deep_nested_module(self):
        """Test extracting module from deeply nested key."""
        result = get_module_from_key("a.b.c.d.x_func")
        assert result == "a.b.c.d"

    def test_class_method(self):
        """Test extracting module from class method key."""
        key = f"app.models.x{CLASS_NAME_SEPARATOR}User{CLASS_NAME_SEPARATOR}save"
        result = get_module_from_key(key)
        assert result == "app.models"


class TestRawFuncNameFromMangled:
    """Tests for raw_func_name_from_mangled function."""

    def test_top_level_function(self):
        """Test converting mangled top-level function to raw name."""
        result = raw_func_name_from_mangled("module.x_foo")
        assert result == "module.foo"

    def test_nested_module(self):
        """Test with nested module path."""
        result = raw_func_name_from_mangled("app.utils.x_helper")
        assert result == "app.utils.helper"

    def test_class_method(self):
        """Test converting mangled class method to raw name."""
        mangled = f"module.x{CLASS_NAME_SEPARATOR}MyClass{CLASS_NAME_SEPARATOR}method"
        result = raw_func_name_from_mangled(mangled)
        assert result == "module.MyClass.method"

    def test_no_module_path(self):
        """Test with no module path (just function name)."""
        result = raw_func_name_from_mangled("x_foo")
        assert result == "foo"

    def test_preserves_non_mangled_parts(self):
        """Test that non-mangled parts are preserved."""
        # This tests edge case where input might not follow expected format
        result = raw_func_name_from_mangled("module.submodule.x_my_long_function_name")
        assert result == "module.submodule.my_long_function_name"

    def test_class_method_no_module(self):
        """Test class method without module prefix."""
        mangled = f"x{CLASS_NAME_SEPARATOR}MyClass{CLASS_NAME_SEPARATOR}method"
        result = raw_func_name_from_mangled(mangled)
        assert result == "MyClass.method"

    def test_deeply_nested_class_method(self):
        """Test with deeply nested module and class method."""
        mangled = f"a.b.c.x{CLASS_NAME_SEPARATOR}Handler{CLASS_NAME_SEPARATOR}process"
        result = raw_func_name_from_mangled(mangled)
        assert result == "a.b.c.Handler.process"
