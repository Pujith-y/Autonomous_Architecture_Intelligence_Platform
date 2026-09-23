import io.shiftleft.codepropertygraph.generated.nodes.Method


def isRealMethod(
  method: Method,
  language: String
): Boolean = {

  hasRealSourceLocation(method) &&

  !isSyntheticName(
    method.name,
    language,
    "method"
  )
}