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


class TestRenderTemplate:
    def test_output_structure(self, temp_dir):
        result = skill_generator.render_template(
            output_dir=temp_dir,
            name="recipes",
            description="A recipe skill.",
            tool_names=["list_documents", "get_document", "search", "ask"],
        )
        assert result == temp_dir / "soliplex-skill-recipes"
        assert result.is_dir()
        pkg = result / "soliplex_skill_recipes"
        skill = pkg / "recipes"
        assert (pkg / "__init__.py").is_file()
        assert (skill / "__init__.py").is_file()
        assert (skill / "SKILL.md").is_file()
        assert (skill / "assets" / ".gitkeep").is_file()
        assert (skill / "scripts" / "__init__.py").is_file()

    def test_includes_selected_scripts(self, temp_dir):
        skill_generator.render_template(
            output_dir=temp_dir,
            name="docs",
            description="A docs skill.",
            tool_names=["search", "ask"],
        )
        scripts = (
            temp_dir
            / "soliplex-skill-docs"
            / "soliplex_skill_docs"
            / "docs"
            / "scripts"
        )
        assert (scripts / "search.py").is_file()
        assert (scripts / "ask.py").is_file()
        assert not (scripts / "list_documents.py").exists()
        assert not (scripts / "get_document.py").exists()
        assert not (scripts / "research.py").exists()

    def test_all_tools(self, temp_dir):
        skill_generator.render_template(
            output_dir=temp_dir,
            name="docs",
            description="A docs skill.",
            tool_names=list(skill_generator.AVAILABLE_TOOLS),
        )
        scripts = (
            temp_dir
            / "soliplex-skill-docs"
            / "soliplex_skill_docs"
            / "docs"
            / "scripts"
        )
        for tool in skill_generator.AVAILABLE_TOOLS:
            assert (scripts / f"{tool}.py").is_file()

    def test_single_tool(self, temp_dir):
        skill_generator.render_template(
            output_dir=temp_dir,
            name="docs",
            description="A docs skill.",
            tool_names=["get_document"],
        )
        scripts = (
            temp_dir
            / "soliplex-skill-docs"
            / "soliplex_skill_docs"
            / "docs"
            / "scripts"
        )
        assert (scripts / "get_document.py").is_file()
        remaining = {
            p.name for p in scripts.glob("*.py") if p.name != "__init__.py"
        }
        assert remaining == {"get_document.py"}

    def test_tool_names_in_init(self, temp_dir):
        skill_generator.render_template(
            output_dir=temp_dir,
            name="recipes",
            description="A recipe skill.",
            tool_names=["search", "ask"],
        )
        init = (
            temp_dir
            / "soliplex-skill-recipes"
            / "soliplex_skill_recipes"
            / "__init__.py"
        )
        content = init.read_text()
        assert '["search", "ask"]' in content

    def test_pyproject_toml(self, temp_dir):
        skill_generator.render_template(
            output_dir=temp_dir,
            name="recipes",
            description="A recipe skill.",
            tool_names=["search"],
        )
        toml = temp_dir / "soliplex-skill-recipes" / "pyproject.toml"
        content = toml.read_text()
        assert 'name = "soliplex-skill-recipes"' in content
        assert 'description = "A recipe skill."' in content
        assert 'recipes = "soliplex_skill_recipes:create_skill"' in content

    def test_skill_md_conditionals(self, temp_dir):
        skill_generator.render_template(
            output_dir=temp_dir,
            name="docs",
            description="A docs skill.",
            tool_names=["search"],
        )
        skill_md = (
            temp_dir
            / "soliplex-skill-docs"
            / "soliplex_skill_docs"
            / "docs"
            / "SKILL.md"
        )
        content = skill_md.read_text()
        assert "**search**" in content
        assert "**ask**" not in content
        assert "**list_documents**" not in content
        assert "**research**" not in content

    def test_skills_ref_validates(self, temp_dir):
        from skills_ref import validator

        skill_generator.render_template(
            output_dir=temp_dir,
            name="recipes",
            description="A recipe skill.",
            tool_names=["list_documents", "search", "ask"],
        )
        skill_dir = (
            temp_dir
            / "soliplex-skill-recipes"
            / "soliplex_skill_recipes"
            / "recipes"
        )
        errors = validator.validate(skill_dir)
        assert errors == []


def _make_fake_lancedb(path):
    path.mkdir()
    (path / "data.lance").touch()
    return path


class TestGenerateSkill:
    def test_end_to_end(self, temp_dir):
        db_path = _make_fake_lancedb(temp_dir / "test.lancedb")
        result = skill_generator.generate_skill(
            db_path=db_path,
            output_dir=temp_dir,
            name="recipes",
            description="A recipe skill.",
            tool_names=["search", "ask"],
        )
        assert result == temp_dir / "soliplex-skill-recipes"
        # lancedb copied into assets
        assets = result / "soliplex_skill_recipes" / "recipes" / "assets"
        assert (assets / "recipes.lancedb").is_dir()
        assert (assets / "recipes.lancedb" / "data.lance").is_file()
        # no haiku.rag.yaml
        assert not (assets / "haiku.rag.yaml").exists()

    def test_with_rag_config(self, temp_dir):
        db_path = _make_fake_lancedb(temp_dir / "test.lancedb")
        rag_config = temp_dir / "haiku.rag.yaml"
        rag_config.write_text("storage:\n  data_dir: /tmp\n")
        result = skill_generator.generate_skill(
            db_path=db_path,
            output_dir=temp_dir,
            name="recipes",
            description="A recipe skill.",
            tool_names=["search"],
            rag_config=rag_config,
        )
        assets = result / "soliplex_skill_recipes" / "recipes" / "assets"
        assert (assets / "haiku.rag.yaml").is_file()
        assert (assets / "haiku.rag.yaml").read_text() == (
            "storage:\n  data_dir: /tmp\n"
        )

    def test_rejects_invalid_name(self, temp_dir):
        db_path = _make_fake_lancedb(temp_dir / "test.lancedb")
        with pytest.raises(ValueError, match="name"):
            skill_generator.generate_skill(
                db_path=db_path,
                output_dir=temp_dir,
                name="Bad-Name",
                description="A skill.",
                tool_names=["search"],
            )

    def test_rejects_invalid_tools(self, temp_dir):
        db_path = _make_fake_lancedb(temp_dir / "test.lancedb")
        with pytest.raises(ValueError, match="Unknown"):
            skill_generator.generate_skill(
                db_path=db_path,
                output_dir=temp_dir,
                name="recipes",
                description="A skill.",
                tool_names=["bogus"],
            )

    def test_rejects_nonexistent_db(self, temp_dir):
        with pytest.raises(ValueError, match="does not exist"):
            skill_generator.generate_skill(
                db_path=temp_dir / "nope.lancedb",
                output_dir=temp_dir,
                name="recipes",
                description="A skill.",
                tool_names=["search"],
            )

    def test_rejects_existing_target(self, temp_dir):
        db_path = _make_fake_lancedb(temp_dir / "test.lancedb")
        (temp_dir / "soliplex-skill-recipes").mkdir()
        with pytest.raises(ValueError, match="already exists"):
            skill_generator.generate_skill(
                db_path=db_path,
                output_dir=temp_dir,
                name="recipes",
                description="A skill.",
                tool_names=["search"],
            )

    def test_skills_ref_validates(self, temp_dir):
        from skills_ref import validator

        db_path = _make_fake_lancedb(temp_dir / "test.lancedb")
        result = skill_generator.generate_skill(
            db_path=db_path,
            output_dir=temp_dir,
            name="recipes",
            description="A recipe skill.",
            tool_names=["list_documents", "search", "ask"],
        )
        skill_dir = result / "soliplex_skill_recipes" / "recipes"
        errors = validator.validate(skill_dir)
        assert errors == []
