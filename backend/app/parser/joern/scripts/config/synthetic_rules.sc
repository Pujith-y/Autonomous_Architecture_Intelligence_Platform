val syntheticRules = Map(

  "python" -> Map(

    "method" -> List(
      "^<module>$",
      "^<body>$",
      "^<metaClassCallHandler>$",
      "^<fakeNew>$",
      ".*<metaClassAdapter>$"
    )
  ),

  "java" -> Map(

    "method" -> List(
      "^<clinit>$",
      "^lambda\\$.*",
      "^access\\$\\d+$"
    )
  ),

  "javascript" -> Map(

    "method" -> List(
      "^:program$",
      "^<global>$",
      "^<fakeNew>$",
      "^<anonymous>.*"
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