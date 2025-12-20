import os
import shutil
import sys
import tempfile
import unittest

# Add scripts directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../scripts")))

from augment_dart_docs import augment_docs

class TestAugmentDartDocs(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.class_dir = os.path.join(self.test_dir, "MyClass")
        os.makedirs(self.class_dir)
        
        self.overview_path = os.path.join(self.class_dir, "overview.md")
        with open(self.overview_path, "w") as f:
            f.write("# Overview for MyClass\n\nExisting content.\n")
            
        self.methods_dir = os.path.join(self.class_dir, "methods")
        os.makedirs(self.methods_dir)
        
        # Create dummy method files
        with open(os.path.join(self.methods_dir, "doSomething.md"), "w") as f:
            f.write("Method docs")
        with open(os.path.join(self.methods_dir, "dispose.md"), "w") as f:
            f.write("Dispose docs")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_augment_adds_methods_section(self):
        augment_docs(self.test_dir)
        
        with open(self.overview_path, "r") as f:
            content = f.read()
            
        self.assertIn("## Methods", content)
        self.assertIn("- [doSomething](methods/doSomething.md)", content)
        self.assertIn("- [dispose](methods/dispose.md)", content)

    def test_augment_adds_properties_and_constructors(self):
        # Setup properties
        props_dir = os.path.join(self.class_dir, "properties")
        os.makedirs(props_dir)
        with open(os.path.join(props_dir, "propA.md"), "w") as f:
            f.write("Prop A")
            
        # Setup constructors
        ctors_dir = os.path.join(self.class_dir, "constructors")
        os.makedirs(ctors_dir)
        with open(os.path.join(ctors_dir, "MyClass.md"), "w") as f:
            f.write("Constructor")

        augment_docs(self.test_dir)
        
        with open(self.overview_path, "r") as f:
            content = f.read()
            
        self.assertIn("## Properties", content)
        self.assertIn("- [propA](properties/propA.md)", content)
        self.assertIn("## Constructors", content)
        self.assertIn("- [MyClass](constructors/MyClass.md)", content)

    def test_augment_does_nothing_if_no_subdirs(self):
        # Create a clean dir with only overview
        clean_dir = os.path.join(self.test_dir, "CleanClass")
        os.makedirs(clean_dir)
        overview = os.path.join(clean_dir, "overview.md")
        with open(overview, "w") as f:
            f.write("# Clean Class")
            
        augment_docs(clean_dir)
        
        with open(overview, "r") as f:
            content = f.read()
            
        self.assertEqual(content, "# Clean Class")

    def test_ignores_non_markdown_files(self):
        # Add a non-md file to methods
        with open(os.path.join(self.methods_dir, "not_doc.txt"), "w") as f:
            f.write("Ignore me")
            
        augment_docs(self.test_dir)
        
        with open(self.overview_path, "r") as f:
            content = f.read()
            
        self.assertIn("- [doSomething](methods/doSomething.md)", content)
        self.assertNotIn("not_doc", content)

    def test_augment_is_idempotent(self):
        augment_docs(self.test_dir)
        
        with open(self.overview_path, "r") as f:
            content_pass_1 = f.read()
            
        # Run again
        augment_docs(self.test_dir)
        
        with open(self.overview_path, "r") as f:
            content_pass_2 = f.read()
            
        self.assertEqual(content_pass_1, content_pass_2)
        # Ensure we didn't duplicate sections
        self.assertEqual(content_pass_2.count("## Methods"), 1)


