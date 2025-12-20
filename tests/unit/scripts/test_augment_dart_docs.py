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

if __name__ == "__main__":
    unittest.main()
