Name:		logback
Version:	1.2.13
Release:	1
Summary:	Logging framework and SLF4J 1.7 binding
Group:		Development/Java
License:	LGPLv2 or EPL
URL:		https://logback.qos.ch/
Source0:	https://github.com/qos-ch/logback/archive/refs/tags/v_%{version}.tar.gz#/logback-%{version}.tar.gz

BuildArch:	noarch
BuildRequires:	python
# Literal, so the first rpmbuild -bs records them before sysjar is installed.
BuildRequires:	maven
BuildRequires:	java-current-devel
BuildRequires:	mvn(org.slf4j:slf4j-api)
# slf4j-api parents this, and a parent POM is not a Requires of the jar.
BuildRequires:	mvn(org.slf4j:slf4j-parent:pom::)
BuildRequires:	mvn(org.codehaus.janino:janino)
# janino-parent ships in the janino RPM. Maven resolves it while loading the janino POM.
BuildRequires:	mvn(org.codehaus.janino:janino-parent:pom::)
BuildRequires:	mvn(javax.servlet:javax.servlet-api)
# The servlet POM parents this.
BuildRequires:	mvn(net.java:jvnet-parent:pom::)
BuildSystem:	maven

Obsoletes:	logback-javadoc < %{version}
Obsoletes:	logback-access < %{version}
Obsoletes:	logback-examples < %{version}

%description
Logback is a logging framework. logback-classic is the SLF4J 1.7
binding. 1.2.13 is the last release on that line. This package ships
logback-core and logback-classic. The access and examples modules are
omitted. SMTP appenders are omitted because JavaMail is not published.
Janino and the servlet API stay optional compile dependencies, matching
upstream. Caller-class lookup loads sun.reflect.Reflection by name.
The compiler release is 8. Tests are skipped.

%prep
%autosetup -n logback-v_%{version}
rm -rf logback-access logback-examples logback-site logback-classic/performance .mvn
python - <<'PY'
import shutil
from pathlib import Path

for path in list(Path(".").rglob("src/test")):
    if path.is_dir():
        shutil.rmtree(path)
for path in Path(".").rglob("*.jar"):
    path.unlink()

removed = []
for rel in (
    "logback-core/src/main/java/ch/qos/logback/core/net/SMTPAppenderBase.java",
    "logback-core/src/main/java/ch/qos/logback/core/net/LoginAuthenticator.java",
    "logback-classic/src/main/java/ch/qos/logback/classic/net/SMTPAppender.java",
):
    path = Path(rel)
    if not path.is_file():
        raise SystemExit("missing " + rel)
    path.unlink()
    removed.append(rel)

calc = Path("logback-classic/src/main/java/ch/qos/logback/classic/spi/PackagingDataCalculator.java")
text = calc.read_text(encoding="utf-8")
old_import = "import sun.reflect.Reflection;\n"
if old_import not in text:
    raise SystemExit("missing Reflection import")
text = text.replace(
    old_import,
    "import java.lang.reflect.InvocationTargetException;\nimport java.lang.reflect.Method;\n",
    1,
)
start = text.find("    private static boolean GET_CALLER_CLASS_METHOD_AVAILABLE")
end = text.find("    public void calculate(", start)
if start < 0 or end < 0:
    raise SystemExit("missing caller-class block")
text = text[:start] + """    // JDK 27 has no sun.reflect.Reflection. Look the method up by name.
    private static final Method GET_CALLER_CLASS_METHOD = callerClassMethod();

    private static Method callerClassMethod() {
        try {
            Class<?> reflection = Class.forName("sun.reflect.Reflection");
            Method method = reflection.getMethod("getCallerClass", int.class);
            method.invoke(null, Integer.valueOf(2));
            return method;
        } catch (Throwable ignored) {
            return null;
        }
    }

""" + text[end:]
old_call = (
    "            if (GET_CALLER_CLASS_METHOD_AVAILABLE) {\n"
    "                callerClass = Reflection.getCallerClass(localFirstCommon + i - missfireCount + 1);\n"
    "            }\n"
)
new_call = (
    "            if (GET_CALLER_CLASS_METHOD != null) {\n"
    "                try {\n"
    "                    callerClass = (Class) GET_CALLER_CLASS_METHOD.invoke(null, Integer.valueOf(localFirstCommon + i - missfireCount + 1));\n"
    "                } catch (IllegalAccessException ex) {\n"
    "                    callerClass = null;\n"
    "                } catch (InvocationTargetException ex) {\n"
    "                    callerClass = null;\n"
    "                }\n"
    "            }\n"
)
if old_call not in text:
    raise SystemExit("missing getCallerClass call")
text = text.replace(old_call, new_call, 1)
if (
    "import sun.reflect.Reflection" in text
    or "GET_CALLER_CLASS_METHOD_AVAILABLE" in text
    or "Reflection.getCallerClass" in text
    or "callerClassMethod" not in text
):
    raise SystemExit("Reflection rewrite failed")
calc.write_text(text, encoding="utf-8")

for path in list(Path(".").rglob("pom.xml")):
    path.unlink()
Path("logback-core/src/main/resources").mkdir(parents=True, exist_ok=True)

plugins = """  <build>
    <plugins>
      <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-compiler-plugin</artifactId>
        <version>3.12.1</version>
        <configuration>
          <release>8</release>
        </configuration>
      </plugin>
      <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-jar-plugin</artifactId>
        <version>3.3.0</version>
      </plugin>
    </plugins>
  </build>
"""

parent = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>ch.qos.logback</groupId>
  <artifactId>logback-parent</artifactId>
  <version>%{version}</version>
  <packaging>pom</packaging>
  <name>Logback-Parent</name>
  <description>logback project pom.xml file</description>
  <url>https://logback.qos.ch/</url>
  <licenses>
    <license>
      <name>Eclipse Public License - v 1.0</name>
      <url>https://www.eclipse.org/legal/epl-v10.html</url>
    </license>
    <license>
      <name>GNU Lesser General Public License</name>
      <url>https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html</url>
    </license>
  </licenses>
  <modules>
    <module>logback-core</module>
    <module>logback-classic</module>
  </modules>
  <properties>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    <maven.compiler.release>8</maven.compiler.release>
  </properties>
</project>
"""

def dep(group, artifact, version, optional=False):
    lines = [
        "    <dependency>",
        "      <groupId>" + group + "</groupId>",
        "      <artifactId>" + artifact + "</artifactId>",
        "      <version>" + version + "</version>",
    ]
    if optional:
        lines.append("      <optional>true</optional>")
    lines.append("    </dependency>")
    return "\n".join(lines)

janino = dep("org.codehaus.janino", "janino", "3.1.12", optional=True)
servlet = dep("javax.servlet", "javax.servlet-api", "4.0.1", optional=True)
core_dep = dep("ch.qos.logback", "logback-core", "%{version}", optional=True)
slf4j = dep("org.slf4j", "slf4j-api", "1.7.36", optional=False)

def module_pom(artifact, name, description, dependencies):
    return """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>ch.qos.logback</groupId>
    <artifactId>logback-parent</artifactId>
    <version>%{version}</version>
  </parent>
  <artifactId>""" + artifact + """</artifactId>
  <name>""" + name + """</name>
  <description>""" + description + """</description>
  <dependencies>
""" + "\n".join(dependencies) + """
  </dependencies>
""" + plugins + """</project>
"""

Path("pom.xml").write_text(parent, encoding="utf-8")
Path("logback-core/pom.xml").write_text(
    module_pom("logback-core", "Logback Core Module", "logback-core module", [janino, servlet]),
    encoding="utf-8",
)
Path("logback-classic/pom.xml").write_text(
    module_pom(
        "logback-classic",
        "Logback Classic Module",
        "logback-classic module",
        [core_dep, slf4j, janino, servlet],
    ),
    encoding="utf-8",
)

core_java = list(Path("logback-core/src/main/java").rglob("*.java"))
classic_java = list(Path("logback-classic/src/main/java").rglob("*.java"))
poms = sorted(str(path) for path in Path(".").rglob("pom.xml"))
classic_pom = Path("logback-classic/pom.xml").read_text(encoding="utf-8")
joined = "\n".join(path.read_text(encoding="utf-8") for path in Path(".").rglob("*.java"))
if (
    removed != [
        "logback-core/src/main/java/ch/qos/logback/core/net/SMTPAppenderBase.java",
        "logback-core/src/main/java/ch/qos/logback/core/net/LoginAuthenticator.java",
        "logback-classic/src/main/java/ch/qos/logback/classic/net/SMTPAppender.java",
    ]
    or len(core_java) != 306
    or len(classic_java) != 155
    or poms != ["logback-classic/pom.xml", "logback-core/pom.xml", "pom.xml"]
    or "<optional>true</optional>" not in classic_pom
    or classic_pom.count("<artifactId>logback-core</artifactId>") != 1
    or "<release>8</release>" not in classic_pom
    or "javax.mail" in joined
    or "import sun.reflect.Reflection" in joined
    or Path("logback-access").exists()
    or Path("logback-examples").exists()
    or Path("logback-site").exists()
):
    raise SystemExit(
        "prep mismatch core=" + str(len(core_java))
        + " classic=" + str(len(classic_java))
        + " poms=" + str(poms)
    )
for needle in ("javax.mail", "jansi", "junit", "groovy", "jetty", "tomcat", "log4j", "SNAPSHOT", "<source>", "<target>"):
    for path in Path(".").rglob("pom.xml"):
        if needle in path.read_text(encoding="utf-8"):
            raise SystemExit(str(path) + " still contains " + needle)
PY

# generate_buildrequires already ran. logback-classic must require logback-core.
%build -p
python - <<'PY'
import xml.etree.ElementTree as ET
from pathlib import Path

ET.register_namespace("", "http://maven.apache.org/POM/4.0.0")

def local(tag):
    return tag.rsplit("}", 1)[-1]

path = Path("logback-classic/pom.xml")
tree = ET.parse(path)
root = tree.getroot()
deps = None
for child in root:
    if local(child.tag) == "dependencies":
        deps = child
if deps is None:
    raise SystemExit("dependencies missing")
cleared = 0
for child in list(deps):
    if local(child.tag) != "dependency":
        continue
    artifact = ""
    for item in child:
        if local(item.tag) == "artifactId":
            artifact = (item.text or "").strip()
    if artifact != "logback-core":
        continue
    for item in list(child):
        if local(item.tag) == "optional":
            child.remove(item)
            cleared += 1
if cleared != 1:
    raise SystemExit("cleared " + str(cleared))
tree.write(path, encoding="UTF-8", xml_declaration=True)
text = path.read_text(encoding="utf-8")
if text.count("<optional>true</optional>") != 2 or "<artifactId>logback-core</artifactId>" not in text:
    raise SystemExit("classic optional flags drifted")
PY

%files -f .mfiles
%doc LICENSE.txt README.md
