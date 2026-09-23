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