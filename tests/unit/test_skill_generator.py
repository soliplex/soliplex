import pytest

from soliplex import skill_generator


class TestAvailableTools:
    def test_all_tools_present(self):
        assert skill_generator.AVAILABLE_TOOLS == {
            "list_documents",
            "get_document",
            "search",
            "ask",
            "research",
        }


class TestValidateMetadata:
    def test_valid(self):
        skill_generator.validate_metadata("recipes", "A skill.")

    def test_valid_with_numbers(self):
        skill_generator.validate_metadata("recipes123", "A skill.")

    def test_rejects_underscores(self):
        with pytest.raises(ValueError, match="name"):
            skill_generator.validate_metadata("my_recipes", "A skill.")

    def test_rejects_hyphens(self):
        with pytest.raises(ValueError, match="identifier"):
            skill_generator.validate_metadata("my-recipes", "A skill.")

    def test_rejects_uppercase(self):
        with pytest.raises(ValueError, match="lowercase"):
            skill_generator.validate_metadata("Recipes", "A skill.")

    def test_rejects_empty_name(self):
        with pytest.raises(ValueError, match="name"):
            skill_generator.validate_metadata("", "A skill.")

    def test_rejects_not_identifier(self):
        with pytest.raises(ValueError, match="identifier"):
            skill_generator.validate_metadata("123abc", "A skill.")

    def test_rejects_spaces_in_name(self):
        with pytest.raises(ValueError, match="name"):
            skill_generator.validate_metadata("my recipes", "A skill.")

    def test_rejects_special_chars(self):
        with pytest.raises(ValueError, match="name"):
            skill_generator.validate_metadata("my@recipes", "A skill.")

    def test_rejects_empty_description(self):
        with pytest.raises(ValueError, match="description"):
            skill_generator.validate_metadata("recipes", "")

    def test_rejects_too_long_description(self):
        with pytest.raises(ValueError, match="description"):
            skill_generator.validate_metadata("recipes", "x" * 1025)


class TestValidateTools:
    def test_valid_single_tool(self):
        skill_generator.validate_tools(["search"])

    def test_valid_multiple_tools(self):
        skill_generator.validate_tools(
            ["list_documents", "get_document", "ask"]
        )

    def test_valid_all_tools(self):
        skill_generator.validate_tools(list(skill_generator.AVAILABLE_TOOLS))

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="at least one"):
            skill_generator.validate_tools([])

    def test_rejects_unknown_tool(self):
        with pytest.raises(ValueError, match="Unknown"):
            skill_generator.validate_tools(["search", "bogus"])


class TestValidateDbPath:
    def test_valid_path(self, temp_dir):
        db_path = temp_dir / "test.lancedb"
        db_path.mkdir()
        skill_generator.validate_db_path(db_path)

    def test_rejects_nonexistent(self, temp_dir):
        db_path = temp_dir / "nonexistent.lancedb"
        with pytest.raises(ValueError, match="does not exist"):
            skill_generator.validate_db_path(db_path)

    def test_rejects_file(self, temp_dir):
        db_path = temp_dir / "test.lancedb"
        db_path.touch()
        with pytest.raises(ValueError, match="not a directory"):
            skill_generator.validate_db_path(db_path)


class TestValidateOutputDir:
    def test_valid_output_dir(self, temp_dir):
        skill_generator.validate_output_dir(temp_dir, "recipes")

    def test_rejects_nonexistent(self, temp_dir):
        output_dir = temp_dir / "nonexistent"
        with pytest.raises(ValueError, match="does not exist"):
            skill_generator.validate_output_dir(output_dir, "recipes")

    def test_rejects_existing_target(self, temp_dir):
        target = temp_dir / "soliplex-skill-recipes"
        target.mkdir()
        with pytest.raises(ValueError, match="already exists"):
            skill_generator.validate_output_dir(temp_dir, "recipes")
