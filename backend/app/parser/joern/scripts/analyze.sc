import io.shiftleft.semanticcpg.language._
import upickle.default._


case class MethodInfo(
  name: String,
  full_name: String,
  filename: String,
  line: Int,
  language: String
) derives ReadWriter

case class ClassInfo(
  name: String,
  full_name: String,
  filename: String,
  line: Int,
  language: String,
  bases: List[String]
) derives ReadWriter

case class Relationship(
  source: String,
  target: String,
  relationship_type: String
) derives ReadWriter

case class AnalysisResult(
  classes: List[ClassInfo],
  methods: List[MethodInfo],
  relationships: List[Relationship]
) derives ReadWriter
// ==========================================
// LAYER A — STRUCTURAL FILTER
// ==========================================

def hasRealSourceLocation(
  filename: String,
  lineNumber: Option[Int]
): Boolean = {

  filename != "<empty>" &&
  filename != "<unknown>" &&
  lineNumber.nonEmpty
}


// ==========================================
// LAYER B — SYNTHETIC NAMING RULES
// ==========================================

val syntheticRules = Map(

  "python" -> Map(

    "method" -> List(
      "^<module>$",
      "^<body>$",
      "^<metaClassCallHandler>$",
      "^<fakeNew>$",
      ".*<metaClassAdapter>$"
    ),

    "type_decl" -> List(
      "^<module>$"
    )
  ),

  "java" -> Map(

    "method" -> List(
      "^<clinit>$",
      "^lambda\\$.*",
      "^access\\$\\d+$"
    ),

    "type_decl" -> List()
  ),

  "javascript" -> Map(

    "method" -> List(
      "^:program$"
    ),

    "type_decl" -> List(
      "^:program$",
      "^<init>$",
      "^<anon-class>\\d+$"
    )
  )
)


def isSyntheticName(
  name: String,
  language: String,
  nodeType: String
): Boolean = {

  syntheticRules
    .get(language)
    .flatMap(_.get(nodeType))
    .getOrElse(List())
    .exists(pattern => name.matches(pattern))
}


// ==========================================
// LAYER C — METHOD SEMANTIC LOGIC
// ==========================================

def isRealMethod(
  method: Method,
  language: String
): Boolean = {

  // ----------------------------------------
  // Layer A

  val hasRealLocation =
    hasRealSourceLocation(
      method.filename,
      method.lineNumber
    )

  // ---------------------------------------- 
  // Layer B
  val hasSyntheticName =
    isSyntheticName(
      method.name,
      language,
      "method"
    )

  // Layer C


  val isConstructor =
    method.name == "<init>"

  // Final decision


  hasRealLocation &&
  !hasSyntheticName &&
  (
    isConstructor ||
    !method.name.startsWith("<")
  )
}

def isRealClass(
  typeDecl: TypeDecl,
  language: String
): Boolean = {

 
  // Layer A — Structural

  val hasRealLocation =
    hasRealSourceLocation(
      typeDecl.filename,
      typeDecl.lineNumber
    )


  // Layer B — Naming

  val hasSyntheticName =
    isSyntheticName(
      typeDecl.name,
      language,
      "type_decl"
    )
  
  // Layer C — Semantic

  val looksLikeClass =
    language match {

      case "python" =>

        typeDecl.astChildren
          .isMethod
          .name("<body>")
          .nonEmpty


      case "java" =>

        typeDecl.code.startsWith("class ") ||
        typeDecl.code.startsWith("interface ") ||
        typeDecl.code.startsWith("enum ")


      case "javascript" =>

        typeDecl.code.startsWith("class ")


      case _ =>
        false
    }

  // Final decision

  hasRealLocation &&
  !hasSyntheticName &&
  looksLikeClass
}


// ==========================================
// MAIN
// ==========================================

@main def main(repository: String): Unit = {

  importCode(repository)

  val methods = cpg.method
    .filter { method =>

      val language =
        detectLanguage(method.filename)

      isRealMethod(method, language)
    }
    .map { method =>

      MethodInfo(
        name = method.name,
        full_name = method.fullName,
        filename = method.filename,
        line = method.lineNumber.getOrElse(0),
        language = detectLanguage(method.filename)
      )
    }
    .toList

  val classes = cpg.typeDecl
    .filter { typeDecl =>

      val language =
        detectLanguage(typeDecl.filename)

      isRealClass(typeDecl, language)
    }
    .map { typeDecl =>

      val language =
        detectLanguage(typeDecl.filename)

      val rawBases = typeDecl
        .inheritsFromTypeFullName
        .filter(isValidBase)
        .distinct
        .toList

      ClassInfo(
        name = typeDecl.name,
        full_name = typeDecl.fullName,
        filename = typeDecl.filename,
        line = typeDecl.lineNumber.getOrElse(0),
        language = language,
        bases = rawBases
      )
    }
    .toList

  val classesByFullName =
    classes
      .map { classInfo =>
        classInfo.full_name -> classInfo
      }
      .toMap
  
  val inheritanceRelationships =
    resolveInheritance(
      classes,
      classesByFullName
    )

  val methodRelationships =
    resolveMethodOwnership(
      methods,
      classesByFullName
    )

  val relationships =
    inheritanceRelationships ++ methodRelationships

  val result =
    AnalysisResult(classes = classes, methods = methods, relationships = relationships)


  println(
    write(result)
  )
}


// ==========================================
// LANGUAGE DETECTION & Helpers
// ==========================================

def detectLanguage(filename: String): String = {

  if (filename.endsWith(".py")) {
    "python"

  } else if (filename.endsWith(".java")) {
    "java"

  } else if (filename.endsWith(".js")) {
    "javascript"

  } else {
    "unknown"
  }
}

def isValidBase(base: String): Boolean = {

  !base.startsWith("<") &&
  base != "ANY" &&
  base != "java.lang.Object"
}


def resolveInheritance(
  classes: List[ClassInfo],
  classesByFullName: Map[String, ClassInfo]
): List[Relationship] = {

  classes.flatMap { child =>

    child.bases
      .filter(classesByFullName.contains)
      .map { baseFullName =>

        Relationship(
          source = child.full_name,
          target = baseFullName,
          relationship_type = "INHERITS_FROM"
        )
      }
  }
}

def resolveMethodOwnership(
  methods: List[MethodInfo],
  classesByFullName: Map[String, ClassInfo]
): List[Relationship] = {

  methods.flatMap { method =>

    val matchingClasses =
      classesByFullName.values
        .filter { classInfo =>
          isMethodOwnedByClass(
            method,
            classInfo
          )
        }
        .toList

    matchingClasses
      .sortBy(_.full_name.length)
      .lastOption
      .map { owner =>

        Relationship(
          source = owner.full_name,
          target = method.full_name,
          relationship_type = "CONTAINS_METHOD"
        )
      }
      .toList
  }
}
def isMethodOwnedByClass(
  method: MethodInfo,
  classInfo: ClassInfo
): Boolean = {

  if (method.language != classInfo.language) {
    false

  } else {

    method.language match {

      case "python" | "java" =>

        method.full_name.startsWith(
          classInfo.full_name + "."
        )


      case "javascript" =>

        method.full_name.startsWith(
          classInfo.full_name + ":"
        )


      case _ =>
        false
    }
  }
}