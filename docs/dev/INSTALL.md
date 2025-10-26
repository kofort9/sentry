# 🚀 One-Liner Installation

## **Install Sentries in One Command**

```bash
# For any repository, run this single command:
curl -sSL https://raw.githubusercontent.com/kofort9/sentries/main/scripts/install_sentries.py | python3 -
```

## **What This Does**

1. **Downloads** the installation script
2. **Checks** your environment (Python, Git, GitHub)
3. **Installs** Sentries package with all dependencies
4. **Sets up** GitHub Actions workflows
5. **Creates** configuration file
6. **Guides** you through next steps

## **Prerequisites**

- Python 3.10+
- Git repository
- GitHub integration (recommended)

## **Alternative Installation Methods**

### **Using pip directly:**
```bash
pip install git+https://github.com/kofort9/sentries.git[all]
```

### **Using the script manually:**
```bash
# Download and run the script
wget https://raw.githubusercontent.com/kofort9/sentries/main/scripts/install_sentries.py
python3 install_sentries.py
```

### **Add to your project:**
```toml
# pyproject.toml
[project.dependencies]
sentries = {git = "https://github.com/kofort9/sentries.git", extras = ["all"]}
```

## **After Installation**

1. **Set up self-hosted runner** with Ollama
2. **Configure GitHub variables** (MODEL_PLAN, MODEL_PATCH)
3. **Test with a PR** to see Sentries in action!

---

**That's it! One command to get AI-powered test and documentation maintenance.** 🎉
