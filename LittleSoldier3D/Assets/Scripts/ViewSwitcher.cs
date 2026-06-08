using UnityEngine;

public class ViewSwitcher : MonoBehaviour
{
    public Transform heroModel;
    public Vector3 fpsLocalPos = new Vector3(0f, 0.6f, 0f);
    public Vector3 tpsLocalPos = new Vector3(0f, 2.2f, -4f);

    private bool thirdPerson = false;
    private Renderer[] heroRenderers;

    void Start()
    {
        if (heroModel != null)
            heroRenderers = heroModel.GetComponentsInChildren<Renderer>();
        Apply();
    }

    void Update()
    {
        if (Input.GetKeyDown(KeyCode.V))
        {
            thirdPerson = !thirdPerson;
            Apply();
        }
    }

    void Apply()
    {
        transform.localPosition = thirdPerson ? tpsLocalPos : fpsLocalPos;

        if (heroRenderers != null)
            foreach (var r in heroRenderers)
                r.enabled = thirdPerson;
    }
}
