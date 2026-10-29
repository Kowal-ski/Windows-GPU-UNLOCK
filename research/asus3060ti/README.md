# ASUS RTX 3060 Ti: experimento Windows

Extensão experimental do [Windows-GPU-UNLOCK de impacifist](https://github.com/impacifist/Windows-GPU-UNLOCK), baseado no [gpu-unlock de Zagitta](https://github.com/Zagitta/gpu-unlock). Código sob a licença do repositório (GPL-2.0). Os autores originais mantêm o crédito pelo mecanismo de unlock.

**Escopo estreito:** uma ASUS RTX 3060 Ti `10de:2489`, subsystem `1043:884f`, GA104 `b74000a1`, 8 GiB, PROM com hash fixado pelo gerador. Não é suporte genérico a todas as 3060 Ti. `proven.json` permanece inalterado; o caminho exige opt-in experimental e evidência local.

No equipamento observado (PRIME B460-PLUS, BIOS 1806, driver Windows 621.01), um boot físico completou a transação e retornou ao Windows. O microbenchmark GEMM apresentou aproximadamente +88% em FP16/BF16 e +90% em TF32. Isso **não mede FPS de jogos ou velocidade de um modelo de IA**. VRAM continua 8 GiB; este trabalho não habilita DLSS Frame Generation nem núcleos físicos extras.

O teste de GEMM aleatório de dois minutos concluiu 17.792 operações, com 278 comparações completas e zero divergências. Temperatura máxima amostrada: 70,84 °C. Não comprova estabilidade prolongada ou compatibilidade de outros equipamentos. Veja [evidência pública](evidence/validation.json), [método](METODO.md) e [possibilidades de pesquisa](POSSIBILIDADES.md).

## Assistente guiado

Requer Windows, Python 3.12+, PowerShell, Git/submódulos do projeto, Clang/lld-link para UEFI, compilador host compatível e assets originais com hashes corretos. Não baixa nem executa ferramentas de terceiros automaticamente. O diagnóstico/status usa apenas a biblioteca padrão; os benchmarks usam numpy e DLLs CUDA existentes.

Execute da raiz do checkout:

```powershell
python research/asus3060ti/assistente.py --action status
python research/asus3060ti/assistente.py --action probe --drive F --clang-efi CAMINHO/clang.exe --lld-link CAMINHO/lld-link.exe
```

Escolha explicitamente a letra do seu USB FAT32. **O assistente substitui o loader removível `EFI/BOOT/BOOTX64.EFI` após salvar backup por hash.** Não formata o pendrive. A identidade da partição é conferida novamente antes da operação; links/junctions nos destinos são recusados. Outros arquivos permanecem preservados.

1. `probe` compila e copia o diagnóstico somente leitura. Use boot manual pelo USB após desligamento completo, com o monitor na RTX.
2. `import --drive F` confere conclusão e hash da PROM, faz cópia verificada no PC e arquiva a coleta no USB. Repita outro desligamento completo/boot/import, sem mudar a BIOS. Uma coleta duplicada não vale como segundo boot.
3. `build --drive F --clang-efi ... --lld-link ... --clang-host ... --assets CAMINHO` analisa as duas coletas, gera o perfil local, executa testes host e compila o pacote. Uma captura local anterior é preservada antes de ser substituída.
4. `stage --drive F --assets CAMINHO` chama o empacotador com suas verificações de evidência. Exige digitar `DESBLOQUEAR`. **O boot seguinte pelo USB tentará unlock automaticamente; Esc em três segundos cancela.** Use o menu de boot manual.

Todas as opções estão em `--help`. Sem `--action`, há um menu textual. Logs/capturas locais ficam em `research/profile/local/` e não devem ser publicados. O assistente orienta a correção de dependências, captura incompleta e topologia incompatível; não altera BIOS, driver, clocks, ordem de boot ou firmware pelo Windows. Uma recusa deve ser investigada, nunca removida para forçar suporte. Se a iGPU ainda aparecer no caminho GOP, ajuste manualmente a BIOS e refaça as duas coletas; não reutilize evidência de outra topologia.

Assets: siga [a preparação oficial do projeto](../../docs/ASSETS.en.md), respeitando a origem, licenças, tamanhos e hashes. Os assets NVIDIA, PROMs, drivers e EFIs personalizados não são distribuídos aqui. A menção a driver 617.14 nessa documentação pertence ao caso original GA102; este experimento usou 621.01 e não altera as versões fixadas dos assets.

Testes locais do assistente (sem tocar em USB real):

```powershell
python research/asus3060ti/test_assistente.py
```

## Medição do barramento

`bandwidth.py` compara cópias RAM→GPU, GPU→RAM e GPU→GPU, com buffers de 16/64/256 MiB e verificação completa. Requer CUDA runtime 12 existente; não muda configurações. `D2D` conta leitura + escrita. Resultados em [bandwidth.json](evidence/bandwidth.json). A atividade de outros aplicativos não foi controlada.

```powershell
python research/asus3060ti/bandwidth.py --cuda-dir CAMINHO/CUDA12 --output resultado.json
```

**English summary:** experimental opt-in for one exact ASUS GA104 board and PROM. One physical Windows boot and bounded numerical tests succeeded. No general hardware support, game/LLM speedup, extra VRAM or DLSS FG claim. Source only; proprietary assets and machine-specific captures are excluded. The Portuguese wizard preserves captures, checks identities/hashes, runs existing profile gates and separates read-only probing from staging a write-capable EFI.

`cpu_ram.py --output resultado-cpu.json` faz uma triagem curta de RAM e GEMM no i3, com processos solicitando quatro/oito threads. Veja resultados e limites no catálogo de possibilidades; isso ainda não é medição de tokens/s.
