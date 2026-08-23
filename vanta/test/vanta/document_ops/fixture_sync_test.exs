defmodule Vanta.FixtureSyncTest do
  use ExUnit.Case, async: true

  @moduletag :docs_consistency

  @docs_root Path.expand("../../../docs/04_experiments/fixtures/document_ops", __DIR__)
  @test_root Path.expand("../../fixtures/document_ops", __DIR__)

  test "document ops docs fixtures and test fixtures remain byte-for-byte synchronized" do
    docs_files = relative_files(@docs_root)
    test_files = relative_files(@test_root)

    assert docs_files == test_files

    Enum.each(docs_files, fn relative_path ->
      docs_content = File.read!(Path.join(@docs_root, relative_path))
      test_content = File.read!(Path.join(@test_root, relative_path))
      assert docs_content == test_content
    end)
  end

  defp relative_files(root) do
    root
    |> Path.join("**/*")
    |> Path.wildcard()
    |> Enum.filter(&File.regular?/1)
    |> Enum.map(fn path ->
      path
      |> Path.relative_to(root)
      |> String.replace("\\", "/")
    end)
    |> Enum.sort()
  end
end
