import io.shiftleft.codepropertygraph.generated.nodes.Method


def hasRealSourceLocation(method: Method): Boolean = {

  method.filename != "<empty>" &&
  method.filename != "<unknown>" &&
  method.lineNumber.nonEmpty
}