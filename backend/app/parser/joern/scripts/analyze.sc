import io.shiftleft.semanticcpg.language._
import ujson._

@main def main(repository: String): Unit = {

  importCode(repository)

  val classes = cpg.typeDecl
    .filter { x =>

      val filename = x.filename
      val code = x.code

      // Java
      val isJavaClass =
        filename.endsWith(".java") &&
        code.startsWith("class ")

      // JavaScript
      val isJavaScriptClass =
        filename.endsWith(".js") &&
        code.startsWith("class ")

      // Python
      val isPythonClass =
        filename.endsWith(".py") &&
        x.astChildren.isMethod.name("<body>").nonEmpty

      isJavaClass || isJavaScriptClass || isPythonClass
    }
    .map { x =>

      val bases =
        x.inheritsFromTypeFullName.l

      Obj(
        "name" -> x.name,
        "full_name" -> x.fullName,
        "filename" -> x.filename,
        "line" -> x.lineNumber.getOrElse(0),
        "bases" -> Arr(
          bases.map(Str(_))* 
        )
      )
    }
    .l

  val result = Obj(
    "classes" -> Arr(classes*)
  )

  println(result.render())
}