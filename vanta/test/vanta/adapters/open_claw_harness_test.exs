defmodule Vanta.OpenClawHarnessTest do
  use ExUnit.Case, async: true

  @moduletag :fast_unit

  @env %{
    openclaw_dir: "~/openclaw",
    agent: "main",
    session_id: "vanta-test-session",
    model: "openai-codex/test-model",
    thinking: "off",
    timeout_seconds: 600,
    wsl_executable: "mock-wsl"
  }

  test "agent script wraps OpenClaw CLI with process-level timeout" do
    script = Vanta.OpenClawHarness.agent_script(@env, "C:\\Temp\\prompt.txt")

    assert script =~ "timeout --kill-after=5s 630s pnpm openclaw"
    assert script =~ "--timeout 600"
    assert script =~ "--session-id 'vanta-test-session'"
    assert script =~ "--model 'openai-codex/test-model'"
    assert script =~ "--thinking 'off'"
    assert script =~ "--message \"$(cat '/mnt/c/Temp/prompt.txt')\""
  end

  test "agent script omits blank optional OpenClaw flags" do
    script =
      @env
      |> Map.merge(%{agent: "", thinking: nil})
      |> Vanta.OpenClawHarness.agent_script("C:\\Temp\\prompt.txt")

    refute script =~ " --agent "
    refute script =~ " --thinking "
    assert script =~ "--session-id 'vanta-test-session'"
    assert script =~ "--model 'openai-codex/test-model'"
  end

  test "run_agent delegates successful output to the supplied decoder and removes temp files" do
    prefix = unique_temp_prefix()
    parent = self()

    command_runner = fn command, args, opts ->
      assert command == "mock-wsl"
      assert ["--", "bash", "-lic", script] = args
      assert script =~ "bash "
      assert script =~ prefix
      assert opts == [stderr_to_stdout: true]

      {"noise\n{\"payloads\":[{\"text\":\"ok\"}]}\n", 0}
    end

    decoder = fn output ->
      send(parent, {:decoder_output, output})
      {:ok, %{decoded: true}}
    end

    assert {:ok, %{decoded: true}} =
             Vanta.OpenClawHarness.run_agent("prompt body", @env,
               temp_prefix: prefix,
               decoder: decoder,
               command_runner: command_runner
             )

    assert_received {:decoder_output, "noise\n{\"payloads\":[{\"text\":\"ok\"}]}\n"}
    assert Path.wildcard(Path.join(System.tmp_dir!(), "#{prefix}_*")) == []
  end

  test "run_agent returns OpenClaw CLI failure tuples without decoding" do
    prefix = unique_temp_prefix()

    command_runner = fn _command, _args, _opts ->
      {"timeout\n", 124}
    end

    decoder = fn _output -> flunk("decoder should not run after CLI failure") end

    assert {:error, {:openclaw_cli_failed, 124, "timeout\n"}} =
             Vanta.OpenClawHarness.run_agent("prompt body", @env,
               temp_prefix: prefix,
               decoder: decoder,
               command_runner: command_runner
             )

    assert Path.wildcard(Path.join(System.tmp_dir!(), "#{prefix}_*")) == []
  end

  defp unique_temp_prefix do
    "vanta_openclaw_harness_test_#{System.unique_integer([:positive])}"
  end
end
